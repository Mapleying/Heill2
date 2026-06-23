import os
import json
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from backend.database import (
    search_camps, get_camp_details, get_airports_for_camp,
    get_camp_coordinates_by_city,
    search_flights_mock, search_hotels_mock,
    search_china_trains_mock,
)
from backend.services.aviasales_client import AviasalesClient
from backend.services.booking_client import BookingClient
from backend.services.china_train_client import ChinaTrainClient

# Tool Schemas for Gemini Function Calling
GEMINI_TOOLS = [
    {
        "functionDeclarations": [
            {
                "name": "search_sport_camps",
                "description": "Search the database for available sports camps matching criteria.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "sport": {
                            "type": "STRING",
                            "description": "Type of sport. Must be one of: tennis, skiing, surfing"
                        },
                        "skill_level": {
                            "type": "STRING",
                            "description": "Skill level. Tennis (ntrp_3.0 - ntrp_7.0), Ski (ski_beginner, ski_intermediate, ski_advanced, ski_expert), Surf (surf_beginner, surf_intermediate, surf_advanced)"
                        },
                        "location": {
                            "type": "STRING",
                            "description": "Country or city to filter, e.g., Spain, France, Portugal"
                        }
                    },
                    "required": ["sport"]
                }
            },
            {
                "name": "get_sport_camp_details",
                "description": "Retrieve full details for a specific camp including schedule, reviews, and available sessions.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "camp_id": {
                            "type": "STRING",
                            "description": "The unique ID of the camp"
                        }
                    },
                    "required": ["camp_id"]
                }
            },
            {
                "name": "search_flights",
                "description": "Search real flights to nearby airports for a camp location. Includes sport equipment fee estimates.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "origin_iata": {
                            "type": "STRING",
                            "description": "3-letter IATA code of origin airport (e.g. LHR, JFK)"
                        },
                        "destination_city": {
                            "type": "STRING",
                            "description": "City of the camp venue (e.g. Murcia, Ericeira, Chamonix)"
                        },
                        "outbound_date": {
                            "type": "STRING",
                            "description": "Outbound departure date (YYYY-MM-DD)"
                        },
                        "equipment_type": {
                            "type": "STRING",
                            "description": "Optional equipment type: skis, snowboard, surfboard"
                        }
                    },
                    "required": ["origin_iata", "destination_city", "outbound_date"]
                }
            },
            {
                "name": "search_hotels",
                "description": "Search real hotels near a camp venue with sport amenity filters.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "city": {
                            "type": "STRING",
                            "description": "City of the camp venue"
                        },
                        "check_in_date": {
                            "type": "STRING",
                            "description": "Hotel check-in date (YYYY-MM-DD). Use the camp session start date."
                        },
                        "check_out_date": {
                            "type": "STRING",
                            "description": "Hotel check-out date (YYYY-MM-DD). Use the camp session end date."
                        },
                        "amenities": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "Desired amenities. E.g. tennis_courts, ski_storage, surf_rinse_station, pool, early_breakfast"
                        }
                    },
                    "required": ["city"]
                }
            },
            {
                "name": "search_china_trains",
                "description": "Search for high-speed rail (CRH/HSR) trains between Chinese cities. Use when the user wants to travel by train within China, e.g. to reach an international airport hub or when planning travel between Chinese cities.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "origin_city": {
                            "type": "STRING",
                            "description": "Departure city in China (e.g. Beijing, Shanghai, Guangzhou, Chengdu)"
                        },
                        "destination_city": {
                            "type": "STRING",
                            "description": "Destination city in China (e.g. Shanghai, Beijing, Shenzhen)"
                        },
                        "date": {
                            "type": "STRING",
                            "description": "Travel date (YYYY-MM-DD). Defaults to today if omitted."
                        },
                        "seat_class": {
                            "type": "STRING",
                            "description": "Optional seat class: second_class, first_class, business"
                        }
                    },
                    "required": ["origin_city", "destination_city"]
                }
            },
            {
                "name": "create_itinerary_draft",
                "description": "Assemble selected camp session, flight, and hotel into a unified itinerary. Runs conflict checks.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "camp_id": {"type": "STRING", "description": "The selected camp ID"},
                        "session_id": {"type": "STRING", "description": "The selected camp session ID"},
                        "flight_id": {"type": "STRING", "description": "The selected outbound flight ID"},
                        "hotel_id": {"type": "STRING", "description": "The selected hotel ID"},
                        "nights": {"type": "INTEGER", "description": "Number of nights for hotel stay"}
                    },
                    "required": ["camp_id", "session_id"]
                }
            }
        ]
    }
]

SYSTEM_PROMPT = """You are Antigravity, an expert AI Sportcation Travel Agent.
Your job is to help users plan sport-focused vacations (tennis, skiing, surfing). The sport camp is the fixed anchor; all logistics are built around it.

## Conversation flow

### 1. Sport & Camp Discovery
- Ask for sport type, skill level, and preferred region/month if not provided.
- Call search_sport_camps to find options. Present 2–4 results with prices and dates.
- Let the user pick a camp before moving on.

### 2. Travel Preferences (ask BEFORE searching flights)
Once the user picks a camp, ask these three questions in a single, friendly message:
  a. **Departure city** – "Where will you be flying from?" (accept city name or airport code)
  b. **Travel party** – "Are you travelling solo, as a couple, or with a group/family?"
  c. **Departure date** – "When would you like to depart? The camp starts [date] — arriving the day before works well."

Wait for the user's reply before calling search_flights or search_hotels.
If the user wants to change any of these details later, update them and re-search.

### 3. Flight & Hotel Search
- Call search_flights using the user's departure city (origin_iata) and their preferred departure date.
- Call search_hotels using the camp city and camp session dates for check-in/check-out.
- Present results clearly with prices. Let the user choose.
- If the user is departing from a Chinese city, proactively offer to search for a train (search_china_trains) to a major hub airport (e.g. Chengdu → Beijing South for international connection).

### 4. China Train Search
- If the user asks about trains within China, call search_china_trains **immediately** — do NOT ask for the date first.
- Use today's date or the soonest plausible date if the user hasn't specified one.
- G trains = high-speed (350 km/h); C trains = intercity express; D trains = fast (200 km/h).
- Present results with train number, departure/arrival times, duration, seat class, and price in CNY and EUR.

### 5. Itinerary Assembly
- Once a flight and hotel are chosen, call create_itinerary_draft.
- Check for scheduling conflicts and flag them.
- Summarise with total estimated cost and booking deep-links.

## Rules
- NEVER invent camps, flights, hotels, or trains. All data must come from tool results.
- Skill level taxonomy: Tennis = NTRP 1.0–7.0 | Ski = Beginner/Intermediate/Advanced/Expert | Surf = Beginner/Intermediate/Advanced
- If a search returns no results, say so clearly and offer alternatives (different dates, nearby airports).
- Be warm, concise, and proactive — anticipate what the user needs next.
"""


async def execute_tool(
    name: str,
    args: Dict[str, Any],
    state: Dict[str, Any],
    aviasales: Optional[AviasalesClient] = None,
    booking: Optional[BookingClient] = None,
    china_train: Optional[ChinaTrainClient] = None,
) -> Dict[str, Any]:
    if name == "search_sport_camps":
        camps = search_camps(
            sport=args.get("sport"),
            skill_level=args.get("skill_level"),
            location=args.get("location"),
        )
        return {"camps": camps}

    elif name == "get_sport_camp_details":
        details = get_camp_details(args.get("camp_id"))
        return {"details": details}

    elif name == "search_flights":
        origin = args.get("origin_iata", "")
        dest_city = args.get("destination_city", "")
        date = args.get("outbound_date", "")
        equip = args.get("equipment_type")
        airports = get_airports_for_camp(dest_city)
        dest_iata_list = [a["iata"] for a in airports]

        if aviasales and dest_iata_list:
            try:
                flights = await aviasales.search_flights(
                    origin_iata=origin,
                    destination_iata_list=dest_iata_list,
                    date=date,
                    equipment_type=equip,
                )
                if not flights:
                    flights = search_flights_mock(origin, dest_city, date, equip)
            except Exception as e:
                flights = search_flights_mock(origin, dest_city, date, equip)
        else:
            flights = search_flights_mock(origin, dest_city, date, equip)

        # Cache for create_itinerary_draft lookup
        for f in flights:
            state.setdefault("_flight_cache", {})[f["flight_id"]] = f

        return {"flights": flights}

    elif name == "search_hotels":
        city = args.get("city", "")
        amenities = args.get("amenities")
        check_in = args.get("check_in_date") or _default_date(0)
        check_out = args.get("check_out_date") or _default_date(7)
        coords = get_camp_coordinates_by_city(city)

        if booking and coords:
            lat, lng = coords
            try:
                hotels = await booking.search_hotels(
                    lat=lat,
                    lng=lng,
                    check_in=check_in,
                    check_out=check_out,
                    amenities=amenities,
                )
                if not hotels:
                    hotels = search_hotels_mock(lat, lng, city, amenities)
            except Exception:
                hotels = search_hotels_mock(
                    coords[0] if coords else 0,
                    coords[1] if coords else 0,
                    city,
                    amenities,
                )
        else:
            lat, lng = coords if coords else (0, 0)
            hotels = search_hotels_mock(lat, lng, city, amenities)

        # Cache for create_itinerary_draft lookup
        for h in hotels:
            state.setdefault("_hotel_cache", {})[h["hotel_id"]] = h

        return {"hotels": hotels}

    elif name == "search_china_trains":
        origin = args.get("origin_city", "")
        dest   = args.get("destination_city", "")
        date   = args.get("date") or _default_date(0)
        seat   = args.get("seat_class")

        if china_train:
            try:
                trains = await china_train.search_trains(origin, dest, date, seat)
            except Exception:
                trains = search_china_trains_mock(origin, dest, date, seat)
        else:
            trains = search_china_trains_mock(origin, dest, date, seat)

        for t in trains:
            state.setdefault("_train_cache", {})[t["train_id"]] = t

        return {"trains": trains}

    elif name == "create_itinerary_draft":
        camp_id = args.get("camp_id")
        session_id = args.get("session_id")
        flight_id = args.get("flight_id")
        hotel_id = args.get("hotel_id")
        nights = args.get("nights", 6)

        camp = get_camp_details(camp_id)
        if not camp:
            return {"error": "Camp not found"}

        session = next((s for s in camp["sessions"] if s["session_id"] == session_id), None)
        if not session:
            return {"error": "Camp session not found"}

        itinerary = {
            "camp": camp,
            "session": session,
            "flight": None,
            "hotel": None,
            "conflict_warnings": [],
            "total_price_eur": session["price_per_person_eur"],
        }

        if flight_id:
            flight = state.get("_flight_cache", {}).get(flight_id)
            if not flight:
                # Fallback: re-search mock (mock agent path)
                for f in search_flights_mock("LHR", camp["location"]["city"], session["start_date"]):
                    if f["flight_id"] == flight_id:
                        flight = f
                        break
            if flight:
                itinerary["flight"] = flight
                itinerary["total_price_eur"] += flight["price_eur"] + flight["equipment_fee_eur"]

        if hotel_id:
            hotel = state.get("_hotel_cache", {}).get(hotel_id)
            if not hotel:
                for h in search_hotels_mock(0, 0, camp["location"]["city"]):
                    if h["hotel_id"] == hotel_id:
                        hotel = h
                        break
            if hotel:
                itinerary["hotel"] = hotel
                itinerary["total_price_eur"] += hotel["price_per_night_eur"] * nights

        # Conflict detection
        if itinerary["flight"]:
            arr = itinerary["flight"].get("arrival_time", "")
            if "19:30" in arr or (arr and arr[11:16] >= "18:00" and session.get("start_date") in arr):
                itinerary["conflict_warnings"].append(
                    "Warning: Flight arrives late — confirm camp check-in is still open."
                )

        state["itinerary"] = itinerary
        return {"itinerary": itinerary}

    return {"error": "Unknown tool"}


def _default_date(offset_days: int) -> str:
    return (datetime.utcnow() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


# ── NLU constants for the mock agent ────────────────────────────────────────

_SPORT_WORDS = {
    "tennis":  ["tennis", "ntrp", "racket", "court"],
    "skiing":  ["ski", "skiing", "snowboard", "slope", "piste", "alpine", "powder"],
    "surfing": ["surf", "surfing", "wave", "surfboard"],
}

_CAMP_KEYWORDS = {
    "tennis-lamanga": ["la manga", "lamanga", "murcia"],
    "tennis-nadal":   ["nadal", "rafa nadal", "rafa", "mallorca", "manacor"],
    "ski-chamonix":   ["chamonix", "mont blanc"],
    "ski-valthorens": ["val thorens", "valthorens"],
    "surf-ericeira":  ["ericeira"],
    "surf-hossegor":  ["hossegor", "landes"],
}

_SELECTION_WORDS = [
    "choose", "select", "pick", "go with", "book it", "book that",
    "that one", "first one", "second one", "that camp", "sounds good",
    "sounds great", "perfect", "great", "love that", "sign me up",
    "i'll take", "yes please", "let's go", "reserve", "looks good",
    "this one", "let me go", "i want that", "i'd like that",
]

# City name / airport → IATA code for departure-origin parsing
_CITY_TO_IATA: Dict[str, str] = {
    # UK & Ireland
    "london": "LON", "heathrow": "LHR", "gatwick": "LGW", "stansted": "STN", "luton": "LTN",
    "manchester": "MAN", "birmingham": "BHX", "edinburgh": "EDI", "glasgow": "GLA",
    "bristol": "BRS", "leeds": "LBA", "newcastle": "NCL", "belfast": "BFS",
    "dublin": "DUB",
    # Western Europe
    "paris": "PAR", "cdg": "CDG", "charles de gaulle": "CDG", "orly": "ORY",
    "amsterdam": "AMS", "schiphol": "AMS",
    "brussels": "BRU",
    "frankfurt": "FRA", "munich": "MUC", "berlin": "BER", "hamburg": "HAM",
    "dusseldorf": "DUS", "cologne": "CGN", "stuttgart": "STR",
    "zurich": "ZRH", "geneva": "GVA", "basel": "BSL",
    "vienna": "VIE",
    "madrid": "MAD", "barcelona": "BCN", "seville": "SVQ", "malaga": "AGP",
    "bilbao": "BIO", "valencia": "VLC",
    "lisbon": "LIS", "porto": "OPO", "faro": "FAO",
    "rome": "FCO", "milan": "MXP", "venice": "VCE", "naples": "NAP", "florence": "FLR",
    "stockholm": "ARN", "oslo": "OSL", "copenhagen": "CPH", "helsinki": "HEL",
    "reykjavik": "REK",
    "warsaw": "WAW", "krakow": "KRK", "prague": "PRG", "budapest": "BUD",
    "bucharest": "OTP", "sofia": "SOF", "athens": "ATH",
    "oslo": "OSL", "bergen": "BGO",
    # Asia-Pacific — cities
    "hong kong": "HKG", "hkg": "HKG",
    "tokyo": "NRT", "osaka": "KIX", "nagoya": "NGO", "fukuoka": "FUK", "sapporo": "CTS",
    "beijing": "PEK", "shanghai": "PVG", "guangzhou": "CAN", "shenzhen": "SZX",
    "chengdu": "CTU", "chongqing": "CKG", "xian": "XIY",
    "singapore": "SIN",
    "seoul": "ICN", "busan": "PUS",
    "taipei": "TPE",
    "bangkok": "BKK", "phuket": "HKT", "chiang mai": "CNX",
    "kuala lumpur": "KUL", "kl": "KUL",
    "jakarta": "CGK", "bali": "DPS", "surabaya": "SUB",
    "manila": "MNL", "cebu": "CEB",
    "ho chi minh": "SGN", "ho chi minh city": "SGN", "hcmc": "SGN", "saigon": "SGN",
    "hanoi": "HAN", "da nang": "DAD", "danang": "DAD",
    "phnom penh": "PNH", "siem reap": "REP",
    "yangon": "RGN", "rangoon": "RGN",
    "vientiane": "VTE",
    "kathmandu": "KTM",
    "colombo": "CMB",
    "dhaka": "DAC",
    "delhi": "DEL", "new delhi": "DEL", "mumbai": "BOM", "bangalore": "BLR",
    "chennai": "MAA", "hyderabad": "HYD", "kolkata": "CCU", "ahmedabad": "AMD",
    "sydney": "SYD", "melbourne": "MEL", "brisbane": "BNE",
    "perth": "PER", "adelaide": "ADL", "auckland": "AKL", "christchurch": "CHC",
    # Asia-Pacific — countries (map to main hub airport)
    "vietnam": "SGN", "viet nam": "SGN",
    "cambodia": "PNH",
    "myanmar": "RGN", "burma": "RGN",
    "laos": "VTE",
    "thailand": "BKK",
    "indonesia": "CGK",
    "philippines": "MNL",
    "malaysia": "KUL",
    "china": "PVG",
    "japan": "NRT",
    "korea": "ICN", "south korea": "ICN",
    "taiwan": "TPE",
    "india": "DEL",
    "australia": "SYD",
    "new zealand": "AKL",
    "nepal": "KTM",
    "sri lanka": "CMB",
    "bangladesh": "DAC",
    # Middle East & Africa — cities
    "dubai": "DXB", "abu dhabi": "AUH", "sharjah": "SHJ",
    "doha": "DOH",
    "riyadh": "RUH", "jeddah": "JED",
    "kuwait": "KWI", "kuwait city": "KWI",
    "bahrain": "BAH", "manama": "BAH",
    "muscat": "MCT",
    "beirut": "BEY", "amman": "AMM", "tel aviv": "TLV",
    "cairo": "CAI", "nairobi": "NBO", "johannesburg": "JNB", "cape town": "CPT",
    "casablanca": "CMN", "lagos": "LOS", "accra": "ACC", "addis ababa": "ADD",
    # Middle East & Africa — countries
    "uae": "DXB", "united arab emirates": "DXB",
    "qatar": "DOH",
    "saudi arabia": "RUH",
    "oman": "MCT",
    "jordan": "AMM",
    "israel": "TLV",
    "egypt": "CAI",
    "kenya": "NBO",
    "south africa": "JNB",
    "ethiopia": "ADD",
    "nigeria": "LOS",
    "ghana": "ACC",
    "morocco": "CMN",
    # Europe — countries (map to main hub)
    "uk": "LHR", "united kingdom": "LHR", "england": "LHR", "britain": "LHR",
    "scotland": "EDI",
    "ireland": "DUB",
    "france": "CDG",
    "germany": "FRA",
    "netherlands": "AMS", "holland": "AMS",
    "belgium": "BRU",
    "switzerland": "ZRH",
    "austria": "VIE",
    "spain": "MAD",
    "portugal": "LIS",
    "italy": "FCO",
    "sweden": "ARN",
    "norway": "OSL",
    "denmark": "CPH",
    "finland": "HEL",
    "poland": "WAW",
    "turkey": "IST",
    "greece": "ATH",
    "czech republic": "PRG", "czechia": "PRG",
    "hungary": "BUD",
    "romania": "OTP",
    "bulgaria": "SOF",
    # Americas — cities
    "new york": "JFK", "nyc": "JFK", "jfk": "JFK", "newark": "EWR", "laguardia": "LGA",
    "los angeles": "LAX",
    "san francisco": "SFO",
    "chicago": "ORD", "miami": "MIA", "boston": "BOS",
    "washington": "IAD", "houston": "IAH", "dallas": "DFW",
    "seattle": "SEA", "denver": "DEN", "las vegas": "LAS", "phoenix": "PHX",
    "atlanta": "ATL", "orlando": "MCO", "detroit": "DTW", "minneapolis": "MSP",
    "toronto": "YYZ", "montreal": "YUL", "vancouver": "YVR",
    "mexico city": "MEX", "cancun": "CUN", "guadalajara": "GDL",
    "sao paulo": "GRU", "rio de janeiro": "GIG", "buenos aires": "EZE",
    "lima": "LIM", "bogota": "BOG", "santiago": "SCL", "quito": "UIO",
    # Americas — countries
    "usa": "JFK", "us": "JFK", "united states": "JFK", "america": "JFK",
    "canada": "YYZ",
    "mexico": "MEX",
    "brazil": "GRU",
    "argentina": "EZE",
    "colombia": "BOG",
    "chile": "SCL",
    "peru": "LIM",
}

_CHECKOUT_WORDS = [
    "checkout", "check out", "finalize", "finalise", "finish", "done",
    "book now", "confirm", "show itinerary", "view itinerary", "show summary",
    "complete", "ready to book", "total cost", "how much total",
]

# Chinese city IATA codes → city name (for train hub suggestions)
_IATA_TO_CHINA_CITY: Dict[str, str] = {
    "PEK": "Beijing", "PKX": "Beijing",
    "PVG": "Shanghai", "SHA": "Shanghai",
    "CAN": "Guangzhou",
    "SZX": "Shenzhen",
    "CTU": "Chengdu",
    "CKG": "Chongqing",
    "XIY": "Xi'an",
    "HGH": "Hangzhou",
    "NKG": "Nanjing",
    "WUH": "Wuhan",
    "TSN": "Tianjin",
    "CSX": "Changsha",
    "CGO": "Zhengzhou",
    "TAO": "Qingdao",
    "TNA": "Jinan",
    "HFE": "Hefei",
    "KMG": "Kunming",
    "KWE": "Guiyang",
    "NNG": "Nanning",
    "HRB": "Harbin",
    "SHE": "Shenyang",
    "DLC": "Dalian",
    "XMN": "Xiamen",
    "FOC": "Fuzhou",
}

# When departing from a Chinese city airport, suggest train to this hub city instead
# (e.g. from Chengdu, take HSR to Beijing for international flight)
_CHINA_CITY_HUB: Dict[str, str] = {
    "CTU": "Beijing", "CKG": "Beijing",
    "XIY": "Beijing", "KMG": "Beijing",
    "KWE": "Guangzhou", "NNG": "Guangzhou",
    "CSX": "Guangzhou", "WUH": "Beijing",
}

_TRAIN_WORDS = [
    "train", "高铁", "火车", "crh", "hsr", "bullet train", "high speed rail",
    "high-speed rail", "railway", "rail", "g train", "d train", "c train",
    "gaotie", "huoche",
]


class ConversationalAgent:
    def __init__(
        self,
        session_id: str,
        gemini_api_key: Optional[str] = None,
        aviasales_token: Optional[str] = None,
        aviasales_marker: Optional[str] = None,
        booking_affiliate_id: Optional[str] = None,
        booking_api_key: Optional[str] = None,
        china_train_api_key: Optional[str] = None,
        china_train_affiliate_id: Optional[str] = None,
    ):
        self.session_id = session_id
        self.gemini_api_key = gemini_api_key  # server-side key; used when frontend provides none
        self.aviasales = (
            AviasalesClient(aviasales_token, aviasales_marker)
            if aviasales_token else None
        )
        self.booking = (
            BookingClient(booking_affiliate_id, booking_api_key)
            if (booking_affiliate_id and booking_api_key) else None
        )
        self.china_train = ChinaTrainClient(china_train_api_key, china_train_affiliate_id)
        self.state: Dict[str, Any] = {
            "history": [],
            "itinerary": None,
            "_flight_cache": {},
            "_hotel_cache": {},
            "_train_cache": {},
            "_last_suggestions": [],
            "_last_shown_camps": [],
            "_pending_camp": None,   # camp selected but awaiting travel info
            "user_profile": {
                "user_id": "user-1",
                "name": "Alex",
                "travel_preferences": {"cabin_class": "economy", "min_stars": 3},
            },
        }

    @staticmethod
    def _is_card_action(msg: str) -> bool:
        """Card-click messages are structured UI commands, not natural language."""
        lower = msg.lower()
        return (
            lower.startswith("add flight ")
            or lower.startswith("add hotel ")
            or (lower.startswith("book ") and not lower.startswith("book train "))
            or any(w in lower for w in _CHECKOUT_WORDS)
        )

    async def get_response(self, user_message: str, api_key: Optional[str] = None) -> str:
        effective_key = api_key or self.gemini_api_key

        # Card-click actions and pending-camp travel-info replies use the direct
        # state-aware handler. We still inject the exchange into Gemini's history
        # so it stays in sync and knows the camp/flight/hotel was already chosen.
        if self._is_card_action(user_message) or self.state.get("_pending_camp"):
            response = await self._run_mock_agent(user_message)
            self.state["history"].append({"role": "user", "parts": [{"text": user_message}]})
            self.state["history"].append({"role": "model", "parts": [{"text": response}]})
            return response

        self.state["history"].append({"role": "user", "parts": [{"text": user_message}]})
        if not effective_key:
            return await self._run_mock_agent(user_message)
        return await self._run_gemini_agent(effective_key)

    # ── NLU helpers ──────────────────────────────────────────────────────────

    def _detect_sport(self, msg_lower: str) -> Optional[str]:
        for sport, words in _SPORT_WORDS.items():
            if any(w in msg_lower for w in words):
                return sport
        return None

    def _detect_skill(self, msg_lower: str, sport: str) -> Optional[str]:
        if sport == "tennis":
            for lvl in ["7.0", "6.5", "6.0", "5.5", "5.0", "4.5", "4.0", "3.5", "3.0"]:
                if lvl in msg_lower:
                    return f"ntrp_{lvl}"
            for word, code in [("advanced", "ntrp_5.0"), ("intermediate", "ntrp_4.0"), ("beginner", "ntrp_3.0")]:
                if word in msg_lower:
                    return code
        elif sport == "skiing":
            for lvl in ["beginner", "intermediate", "advanced", "expert"]:
                if lvl in msg_lower:
                    return f"ski_{lvl}"
        elif sport == "surfing":
            for lvl in ["beginner", "intermediate", "advanced"]:
                if lvl in msg_lower:
                    return f"surf_{lvl}"
        return None

    def _find_camp_in_message(self, msg_lower: str) -> Optional[Dict]:
        """Return a camp if the message references one by ID, name, or natural selection."""
        for camp in search_camps():
            if camp["camp_id"] in msg_lower:
                return camp
        for camp_id, keywords in _CAMP_KEYWORDS.items():
            if any(kw in msg_lower for kw in keywords):
                return get_camp_details(camp_id)
        last = self.state.get("_last_shown_camps", [])
        if last and any(w in msg_lower for w in _SELECTION_WORDS):
            if any(w in msg_lower for w in ["second", "2nd", "option 2", "second one"]):
                return last[1] if len(last) > 1 else last[0]
            if any(w in msg_lower for w in ["third", "3rd", "option 3", "third one"]):
                return last[2] if len(last) > 2 else last[0]
            return last[0]
        return None

    # ── Travel-info helpers ───────────────────────────────────────────────────

    def _parse_origin(self, msg_lower: str) -> Optional[str]:
        import re
        known_iatas = {v for v in _CITY_TO_IATA.values()}

        # 1. City name lookup — longest match first to avoid "man" matching "manchester"
        for city in sorted(_CITY_TO_IATA, key=len, reverse=True):
            if city in msg_lower:
                return _CITY_TO_IATA[city]

        # 2. Bare 3-letter token that is a known IATA code (e.g. "HKG", "CDG")
        for token in re.findall(r'\b([a-zA-Z]{3})\b', msg_lower):
            if token.upper() in known_iatas:
                return token.upper()

        # 3. Context extraction: text after "from", "flying from", etc.
        m = re.search(
            r'(?:flying from|fly from|depart(?:ing)? from|from|based in)\s+([a-zA-Z][a-zA-Z\s]{1,24}?)(?:\s*[,.]|$)',
            msg_lower,
        )
        if m:
            candidate = m.group(1).strip()
            for city in sorted(_CITY_TO_IATA, key=len, reverse=True):
                if city in candidate or candidate in city:
                    return _CITY_TO_IATA[city]

        return None  # unknown — caller should ask for clarification

    def _parse_travelers(self, msg_lower: str) -> int:
        import re
        if any(w in msg_lower for w in ["solo", "alone", "just me", "by myself", "only me", "1 person", "one person"]):
            return 1
        if any(w in msg_lower for w in ["couple", "partner", "wife", "husband", "girlfriend", "boyfriend", "2 of us", "two of us"]):
            return 2
        m = re.search(r'family of (\d+)', msg_lower)
        if m:
            return int(m.group(1))
        if "family" in msg_lower:
            return 4
        for word, n in [("two", 2), ("three", 3), ("four", 4), ("five", 5), ("six", 6)]:
            if word in msg_lower:
                return n
        m = re.search(r'(\d+)\s*(?:people|person|travelers?|adults?|of us|pax)', msg_lower)
        if m:
            return max(1, min(int(m.group(1)), 9))
        return 1  # default solo

    def _parse_departure_date(self, msg_lower: str, camp_start_date: str) -> str:
        import re
        camp_start = datetime.strptime(camp_start_date, "%Y-%m-%d")

        # "day before" / "night before"
        if "day before" in msg_lower or "night before" in msg_lower or "eve" in msg_lower:
            return (camp_start - timedelta(days=1)).strftime("%Y-%m-%d")

        # "X days before"
        m = re.search(r'(\d+)\s*days?\s*before', msg_lower)
        if m:
            return (camp_start - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")

        # Explicit month + day pattern, e.g. "July 4", "4th July", "4 July"
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
            "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
            "november": 11, "december": 12, "jan": 1, "feb": 2, "mar": 3,
            "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
            "nov": 11, "dec": 12,
        }
        for mname, mnum in months.items():
            if mname in msg_lower:
                day_m = re.search(r'(\d{1,2})(?:st|nd|rd|th)?', msg_lower)
                if day_m:
                    try:
                        d = datetime(camp_start.year, mnum, int(day_m.group(1)))
                        return d.strftime("%Y-%m-%d")
                    except ValueError:
                        pass

        # Explicit YYYY-MM-DD
        m = re.search(r'(\d{4}-\d{2}-\d{2})', msg_lower)
        if m:
            return m.group(1)

        # Default: day before camp
        return (camp_start - timedelta(days=1)).strftime("%Y-%m-%d")

    def _ask_travel_questions(self, camp: Dict) -> str:
        session = camp["sessions"][0]
        return (
            f"**{camp['name']}** — great choice!\n"
            f"Camp dates: **{session['start_date']} → {session['end_date']}** · €{session['price_per_person_eur']:.0f}\n\n"
            f"Before I search flights and hotels, I need a few details:\n\n"
            f"1. **Where are you flying from?** (city or airport code — e.g. London, Paris, JFK)\n"
            f"2. **Traveling solo or with others?** (e.g. solo, couple, family of 4)\n"
            f"3. **When would you like to depart?** The camp starts **{session['start_date']}** — arriving the day before works well.\n\n"
            f"Feel free to answer all three in one message!"
        )

    async def _handle_travel_info(self, msg: str, msg_lower: str) -> str:
        """Parse the user's travel details and proceed to flight/hotel search."""
        camp = self.state["_pending_camp"]
        session = camp["sessions"][0]

        origin_iata = self._parse_origin(msg_lower)
        travelers   = self._parse_travelers(msg_lower)
        depart_date = self._parse_departure_date(msg_lower, session["start_date"])

        # If we couldn't identify the departure city, ask instead of guessing
        if not origin_iata:
            import re as _re
            # Try to extract what the user wrote so we can echo it back
            m = _re.search(
                r'(?:from|flying from|depart(?:ing)? from|based in)\s+([A-Za-z][A-Za-z\s]{1,24}?)(?:\s*[,.]|$)',
                msg,
            )
            city_typed = m.group(1).strip() if m else msg.strip()
            return (
                f"I don't recognise **{city_typed}** as an airport or city yet.\n\n"
                f"Could you give me the **3-letter airport code**? For example:\n"
                f"- Hong Kong → **HKG**\n"
                f"- Tokyo → **NRT** (Narita) or **HND** (Haneda)\n"
                f"- New York → **JFK** or **EWR**\n\n"
                f"You can find it on [IATA's airport search](https://www.iata.org/en/publications/directories/code-search/)."
            )

        travelers_label = f"{travelers} traveler{'s' if travelers > 1 else ''}"
        self.state["_pending_camp"] = None  # consumed

        result = await self._camp_selected_flow(
            camp,
            origin_iata=origin_iata,
            travelers=travelers,
            departure_date=depart_date,
        )
        confirmation = (
            f"Got it — flying from **{origin_iata}**, **{travelers_label}**, departing **{depart_date}**.\n\n"
        )
        return confirmation + result

    async def _camp_selected_flow(self, selected_camp: Dict, origin_iata: str = "LHR", travelers: int = 1, departure_date: Optional[str] = None) -> str:
        """Build draft itinerary and search flights + hotels after a camp is chosen."""
        session = selected_camp["sessions"][0]
        if not departure_date:
            departure_date = (
                datetime.strptime(session["start_date"], "%Y-%m-%d") - timedelta(days=1)
            ).strftime("%Y-%m-%d")
        await execute_tool(
            "create_itinerary_draft",
            {"camp_id": selected_camp["camp_id"], "session_id": session["session_id"]},
            self.state,
        )
        flight_result = await execute_tool(
            "search_flights",
            {
                "origin_iata": origin_iata,
                "destination_city": selected_camp["location"]["city"],
                "outbound_date": departure_date,
            },
            self.state, aviasales=self.aviasales,
        )
        hotel_result = await execute_tool(
            "search_hotels",
            {
                "city": selected_camp["location"]["city"],
                "check_in_date": session["start_date"],
                "check_out_date": session["end_date"],
            },
            self.state, booking=self.booking,
        )

        # When departing from a Chinese city, also search trains to a major hub
        china_hub = _CHINA_CITY_HUB.get(origin_iata)
        if china_hub and china_hub != origin_iata:
            hub_city = _IATA_TO_CHINA_CITY.get(origin_iata, "")
            if hub_city:
                await execute_tool(
                    "search_china_trains",
                    {"origin_city": hub_city, "destination_city": china_hub, "date": departure_date},
                    self.state, china_train=self.china_train,
                )
        flights = flight_result.get("flights", [])
        hotels  = hotel_result.get("hotels", [])
        data_note = " (live)" if self.aviasales else " (sample)"

        self.state["_last_suggestions"] = [
            {
                "type": "flight",
                "label": f"{f['airline']} · {f['origin']} → {f['destination']}",
                "sublabel": f"{f['stops']} stop{'s' if f['stops'] != 1 else ''} · {f['departure_time'][:10]}",
                "price": f"€{f['price_eur']:.0f}",
                "action": f"Add flight {f['flight_id']}",
                "booking_link": f['booking_link'],
            }
            for f in flights[:3]
        ] + [
            {
                "type": "hotel",
                "label": f"{h['name']} · {h['stars']}★",
                "sublabel": "Sport Partner ✓" if h.get('sport_partner') else "",
                "price": f"€{h['price_per_night_eur']:.0f}/night",
                "action": f"Add hotel {h['hotel_id']}",
                "booking_link": h.get('booking_link', ''),
            }
            for h in hotels[:3]
        ]
        n_f, n_h = len(flights), len(hotels)
        return (
            f"Confirmed! **{selected_camp['name']}** · "
            f"{session['start_date']} → {session['end_date']} · "
            f"€{session['price_per_person_eur']:.0f}\n\n"
            f"Found **{n_f} flight{'s' if n_f != 1 else ''}**{data_note} and "
            f"**{n_h} hotel{'s' if n_h != 1 else ''}** nearby.\n"
            f"Click a card below to add it, or type **checkout** when ready."
        )

    # ── China train handler ───────────────────────────────────────────────────

    async def _handle_china_train_search(self, msg: str, msg_lower: str) -> str:
        import re as _re
        from backend.database import CHINA_STATION_MAP

        # Extract origin and destination from message
        # Patterns: "from X to Y", "train to Y from X"
        origin_city = None
        dest_city   = None

        m = _re.search(
            r'(?:from|depart(?:ing)? from)\s+([A-Za-z\']+)\s+to\s+([A-Za-z\']+)\b',
            msg, _re.IGNORECASE
        )
        if m:
            origin_city = m.group(1).strip()
            dest_city   = m.group(2).strip()
        else:
            m2 = _re.search(
                r'\bto\s+([A-Za-z\']+)\s+from\s+([A-Za-z\']+)\b',
                msg, _re.IGNORECASE
            )
            if m2:
                dest_city   = m2.group(1).strip()
                origin_city = m2.group(2).strip()

        # Validate against known stations
        known_cities = list(CHINA_STATION_MAP.keys())
        if not origin_city or not dest_city:
            # Ask for clarification
            examples = ", ".join(c.title() for c in list(CHINA_STATION_MAP.keys())[:8])
            return (
                "I can search high-speed rail (CRH) trains between Chinese cities!\n\n"
                f"Just tell me the **origin** and **destination**, e.g.:\n"
                f"- \"Search trains from Beijing to Shanghai\"\n"
                f"- \"Find a train from Guangzhou to Shenzhen on July 10\"\n\n"
                f"Supported cities include: {examples}, and more."
            )

        # Parse date from message
        date = self._parse_departure_date(msg_lower, _default_date(1))

        result = await execute_tool(
            "search_china_trains",
            {"origin_city": origin_city, "destination_city": dest_city, "date": date},
            self.state, china_train=self.china_train,
        )
        trains = result.get("trains", [])
        if not trains:
            return (
                f"No trains found from **{origin_city.title()}** to **{dest_city.title()}** on {date}.\n\n"
                f"Try a different date or check that both cities have HSR stations."
            )

        self.state["_last_suggestions"] = self._suggestions_from_tool("search_china_trains", result)

        orig_station = trains[0]["origin_station"]
        dest_station = trains[0]["destination_station"]
        lines = [
            f"Found **{len(trains)} train{'s' if len(trains) > 1 else ''}** "
            f"from **{orig_station}** → **{dest_station}** on {date}:\n"
        ]
        for t in trains:
            lines.append(
                f"- **{t['train_number']}** ({t['train_type']}) · "
                f"{t['departure_time'][11:]} → {t['arrival_time'][11:]} · "
                f"{t['duration']} · {t['seat_class']} · "
                f"¥{t['price_cny']:.0f} (~€{t['price_eur']:.0f})"
            )
        lines.append("\nClick a card to book, or ask me to search a different class or date.")
        return "\n".join(lines)

    # ── Main mock agent ───────────────────────────────────────────────────────

    async def _run_mock_agent(self, msg: str) -> str:
        msg_lower = msg.lower()
        self.state["_last_suggestions"] = []

        # 1. Checkout
        if any(w in msg_lower for w in _CHECKOUT_WORDS):
            itin = self.state.get("itinerary")
            if not itin:
                return "You don't have a draft itinerary yet. Tell me which sport you'd like to plan!"
            camp = itin["camp"]; session = itin["session"]
            flight = itin["flight"]; hotel = itin["hotel"]
            summary = "### Your Sportcation Itinerary\n\n"
            summary += f"1. **Camp:** {camp['name']} ({camp['location']['city']})\n"
            summary += f"   - Dates: {session['start_date']} to {session['end_date']}\n\n"
            if hotel:
                summary += f"2. **Hotel:** {hotel['name']} ({hotel['stars']}★) · €{hotel['price_per_night_eur']}/night\n"
                summary += f"   - [Book Hotel]({hotel['booking_link']})\n\n"
            else:
                summary += "2. **Hotel:** Not selected yet\n\n"
            if flight:
                summary += f"3. **Flight:** {flight['airline']} {flight['origin']} → {flight['destination']} · €{flight['price_eur']}\n"
                summary += f"   - [Book Flight]({flight['booking_link']})\n\n"
            else:
                summary += "3. **Flight:** Not selected yet\n\n"
            summary += f"**Total Estimated Cost:** €{itin['total_price_eur']:.2f}\n"
            if itin.get("conflict_warnings"):
                summary += "\n⚠️ **Conflicts:**\n" + "\n".join(f"- {w}" for w in itin["conflict_warnings"])
            return f"{summary}\nUse the sidebar buttons to export as PDF or .ics calendar!"

        # 2. Add flight (card click sends "Add flight <id>")
        import re as _re
        if "add flight" in msg_lower or (
            "flight" in msg_lower and any(x in msg_lower for x in ["aviasales-", "flight-"])
        ):
            ids = _re.findall(r'(?:aviasales|flight)-[\w\-]+', msg)
            flight_id = ids[0] if ids else None
            if not self.state.get("itinerary"):
                return "Please choose a camp first so I can anchor the flight around it!"
            itin = self.state["itinerary"]
            await execute_tool("create_itinerary_draft", {
                "camp_id": itin["camp"]["camp_id"],
                "session_id": itin["session"]["session_id"],
                "flight_id": flight_id,
                "hotel_id": itin["hotel"]["hotel_id"] if itin.get("hotel") else None,
            }, self.state)
            name = self.state["itinerary"]["flight"]["airline"] if self.state["itinerary"].get("flight") else "Flight"
            warns = ""
            if self.state["itinerary"].get("conflict_warnings"):
                warns = "\n\n⚠️ " + " ".join(self.state["itinerary"]["conflict_warnings"])
            return f"**{name}** added to your itinerary!{warns}\n\nAdd a hotel or type **checkout** to review."

        # 3. Add hotel (card click sends "Add hotel <id>")
        if "add hotel" in msg_lower or (
            "hotel" in msg_lower and any(x in msg_lower for x in ["booking-", "hotel-"])
        ):
            ids = _re.findall(r'(?:booking|hotel)-[\w\-]+', msg)
            hotel_id = ids[0] if ids else None
            if not self.state.get("itinerary"):
                return "Please choose a camp first!"
            itin = self.state["itinerary"]
            await execute_tool("create_itinerary_draft", {
                "camp_id": itin["camp"]["camp_id"],
                "session_id": itin["session"]["session_id"],
                "flight_id": itin["flight"]["flight_id"] if itin.get("flight") else None,
                "hotel_id": hotel_id,
            }, self.state)
            name = self.state["itinerary"]["hotel"]["name"] if self.state["itinerary"].get("hotel") else "Hotel"
            return f"**{name}** added! Type **checkout** to see your full itinerary and booking links."

        # 3b. Book train (card click sends "Book train <id>")
        import re as _re
        if msg_lower.startswith("book train "):
            ids = _re.findall(r'crh-[\w\-]+', msg_lower)
            train_id = ids[0] if ids else None
            train = self.state.get("_train_cache", {}).get(train_id)
            if train:
                return (
                    f"**{train['train_number']}** ({train['train_type']}) · "
                    f"{train['origin_station']} → {train['destination_station']}\n"
                    f"Departs {train['departure_time']} · Arrives {train['arrival_time']} · "
                    f"{train['duration']} · {train['seat_class']}\n"
                    f"Price: ¥{train['price_cny']:.0f} (~€{train['price_eur']:.0f})\n\n"
                    f"[Book on Trip.com]({train['booking_link']})"
                )
            return "Couldn't find that train. Please search again to get fresh results."

        # 4. Travel info reply — user is answering the departure questions
        if self.state.get("_pending_camp"):
            return await self._handle_travel_info(msg, msg_lower)

        # 4b. China train search intent
        if any(w in msg_lower for w in _TRAIN_WORDS):
            return await self._handle_china_train_search(msg, msg_lower)

        # 5. Camp selected — by name, city, ID, or natural selection after seeing a list
        selected = self._find_camp_in_message(msg_lower)
        if selected:
            self.state["_pending_camp"] = selected
            return self._ask_travel_questions(selected)

        # 6. Sport discovery — detect sport + optional skill/location filters
        sport = self._detect_sport(msg_lower)
        if sport:
            skill = self._detect_skill(msg_lower, sport)
            location = next(
                (loc for loc in ["spain", "france", "portugal", "murcia", "mallorca",
                                 "chamonix", "val thorens", "ericeira", "hossegor"]
                 if loc in msg_lower),
                None,
            )
            camps = search_camps(sport=sport, skill_level=skill, location=location)
            self.state["_last_shown_camps"] = camps

            if not camps:
                sport_label = {"tennis": "tennis", "skiing": "ski", "surfing": "surf"}[sport]
                return f"No {sport_label} camps matched those filters. Try broadening your search!"

            self.state["_last_suggestions"] = [
                {
                    "type": "camp",
                    "label": f"{c['name']} · {c['location']['city']}, {c['location']['country_code']}",
                    "sublabel": f"{c['average_review_score']}★ · {c['skill_level_min']} → {c['skill_level_max']}",
                    "price": f"from €{min(s['price_per_person_eur'] for s in c['sessions']):.0f}",
                    "action": f"Book {c['camp_id']}",
                    "booking_link": "",
                }
                for c in camps[:4]
            ]
            intro = {
                "tennis":  "Here are available tennis camps",
                "skiing":  "Let's hit the slopes — here are ski camps",
                "surfing": "Catch some waves — here are surf camps",
            }[sport]
            suffix     = f" in {location.title()}" if location else ""
            skill_note = f" for **{skill}**" if skill else ""
            return f"{intro}{suffix}{skill_note}. Click a camp card below to select it!"

        # 7. Context-aware default
        if self.state.get("itinerary"):
            camp_name = self.state["itinerary"]["camp"]["name"]
            return (
                f"You have **{camp_name}** anchored. "
                f"Add a flight or hotel using the cards, or type **checkout** to finalise."
            )
        return (
            "I'm Antigravity, your sportcation planner! Which sport are you interested in?\n\n"
            "- **Tennis** — camps in Spain\n"
            "- **Skiing** — Chamonix or Val Thorens, France\n"
            "- **Surfing** — Portugal or France"
        )

    def _suggestions_from_tool(self, name: str, result: Dict[str, Any]) -> List[Dict]:
        if name == "search_sport_camps":
            camps = result.get("camps", [])
            self.state["_last_shown_camps"] = camps
            return [
                {
                    "type": "camp",
                    "label": f"{c['name']} · {c['location']['city']}, {c['location']['country_code']}",
                    "sublabel": f"{c['average_review_score']}★ · {c['skill_level_min']} → {c['skill_level_max']}",
                    "price": f"from €{min(s['price_per_person_eur'] for s in c['sessions']):.0f}",
                    "action": f"Book {c['camp_id']}",
                    "booking_link": "",
                }
                for c in camps[:4]
            ]
        if name == "search_flights":
            return [
                {
                    "type": "flight",
                    "label": f"{f['airline']} · {f['origin']} → {f['destination']}",
                    "sublabel": f"{f['stops']} stop{'s' if f['stops'] != 1 else ''} · {f['departure_time'][:10]}",
                    "price": f"€{f['price_eur']:.0f}",
                    "action": f"Add flight {f['flight_id']}",
                    "booking_link": f["booking_link"],
                }
                for f in result.get("flights", [])[:3]
            ]
        if name == "search_hotels":
            return [
                {
                    "type": "hotel",
                    "label": f"{h['name']} · {h['stars']}★",
                    "sublabel": "Sport Partner ✓" if h.get("sport_partner") else "",
                    "price": f"€{h['price_per_night_eur']:.0f}/night",
                    "action": f"Add hotel {h['hotel_id']}",
                    "booking_link": h.get("booking_link", ""),
                }
                for h in result.get("hotels", [])[:3]
            ]
        if name == "search_china_trains":
            return [
                {
                    "type": "train",
                    "label": f"{t['train_number']} ({t['train_type']}) · {t['origin_city']} → {t['destination_city']}",
                    "sublabel": f"{t['departure_time'][11:]} → {t['arrival_time'][11:]} · {t['duration']} · {t['seat_class']}",
                    "price": f"¥{t['price_cny']:.0f} (~€{t['price_eur']:.0f})",
                    "action": f"Book train {t['train_id']}",
                    "booking_link": t.get("booking_link", ""),
                }
                for t in result.get("trains", [])[:4]
            ]
        return []

    async def _call_gemini(self, api_key: str, payload: dict) -> Optional[httpx.Response]:
        """Try gemini-2.5-flash, fall back to gemini-2.0-flash on 503/429."""
        base = "https://generativelanguage.googleapis.com/v1beta/models"
        models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]
        for model in models:
            url = f"{base}/{model}:generateContent?key={api_key}"
            for attempt in range(3):
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
                if response.status_code not in (429, 503):
                    break
                await __import__("asyncio").sleep(2 ** attempt)
            if response.status_code == 200:
                return response
            status = response.status_code
            try:
                err_msg = response.json().get("error", {}).get("message", response.text[:200])
            except Exception:
                err_msg = response.text[:200]
            print(f"[GEMINI] model={model} status={status} err={err_msg}")
            if status not in (429, 503):
                # Auth or bad-request error — no point trying next model
                return response
        return response  # last response (both models failed)

    async def get_response_stream(self, user_message: str, api_key: Optional[str] = None):
        """Async generator yielding {"text": "..."} chunks, then {"done": True, ...}."""
        effective_key = api_key or self.gemini_api_key

        if self._is_card_action(user_message) or self.state.get("_pending_camp"):
            response = await self._run_mock_agent(user_message)
            self.state["history"].append({"role": "user", "parts": [{"text": user_message}]})
            self.state["history"].append({"role": "model", "parts": [{"text": response}]})
            yield {"text": response}
            return

        self.state["history"].append({"role": "user", "parts": [{"text": user_message}]})

        if not effective_key:
            response = await self._run_mock_agent(user_message)
            yield {"text": response}
            return

        async for chunk in self._stream_gemini_agent(effective_key):
            yield chunk

    async def _stream_gemini_agent(self, api_key: str):
        """Streams Gemini tokens; executes tool calls internally between rounds."""
        import asyncio
        self.state["_last_suggestions"] = []
        contents = self.state["history"]
        base = "https://generativelanguage.googleapis.com/v1beta/models"
        models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]

        for _ in range(5):
            payload = {
                "contents": contents,
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "tools": GEMINI_TOOLS,
            }

            text_parts: List[str] = []
            func_parts: List[Dict] = []
            streamed_any = False
            got_response = False

            for model in models:
                url = f"{base}/{model}:streamGenerateContent?alt=sse&key={api_key}"
                text_parts, func_parts = [], []

                try:
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        async with client.stream("POST", url, json=payload, headers={"Content-Type": "application/json"}) as resp:
                            if resp.status_code in (429, 503):
                                await resp.aread()
                                await asyncio.sleep(1)
                                continue
                            if resp.status_code != 200:
                                body = await resp.aread()
                                try:
                                    err_msg = json.loads(body).get("error", {}).get("message", "")
                                except Exception:
                                    err_msg = body.decode()[:200]
                                print(f"[GEMINI STREAM] {model} {resp.status_code}: {err_msg}")
                                if resp.status_code in (401, 403):
                                    yield {"text": f"Error: API key rejected — {err_msg}"}
                                    return
                                continue

                            async for line in resp.aiter_lines():
                                if not line.startswith("data: "):
                                    continue
                                data_str = line[6:].strip()
                                if not data_str:
                                    continue
                                try:
                                    chunk = json.loads(data_str)
                                except json.JSONDecodeError:
                                    continue
                                candidates = chunk.get("candidates", [])
                                if not candidates:
                                    continue
                                for part in candidates[0].get("content", {}).get("parts", []):
                                    if "text" in part and part["text"]:
                                        text_parts.append(part["text"])
                                        if not func_parts:
                                            yield {"text": part["text"]}
                                            streamed_any = True
                                    elif "functionCall" in part:
                                        func_parts.append(part)

                            got_response = True
                            break
                except Exception as e:
                    print(f"[GEMINI STREAM] {model} exception: {e}")
                    continue

            if not got_response:
                fallback = await self._run_mock_agent(contents[-1]["parts"][0]["text"])
                if not streamed_any:
                    yield {"text": fallback}
                return

            full_content: Dict[str, Any] = {"role": "model", "parts": []}
            if text_parts:
                full_content["parts"].append({"text": "".join(text_parts)})
            full_content["parts"].extend(func_parts)
            self.state["history"].append(full_content)

            function_calls = [p["functionCall"] for p in func_parts]
            if not function_calls:
                return  # text already streamed

            tool_content: Dict[str, Any] = {"role": "function", "parts": []}
            round_suggestions: List[Dict] = []
            for call in function_calls:
                name = call.get("name")
                args = call.get("args", {})
                result = await execute_tool(name, args, self.state, aviasales=self.aviasales, booking=self.booking, china_train=self.china_train)
                tool_content["parts"].append({"functionResponse": {"name": name, "response": result}})
                round_suggestions += self._suggestions_from_tool(name, result)

            if round_suggestions:
                self.state["_last_suggestions"] = round_suggestions

            self.state["history"].append(tool_content)
            contents = self.state["history"]

        if not streamed_any:
            yield {"text": "Max iterations reached without a final response."}

    async def _run_gemini_agent(self, api_key: str) -> str:
        """Agentic loop using Gemini Function Calling with real flight/hotel APIs."""
        contents = self.state["history"]
        self.state["_last_suggestions"] = []

        for _ in range(5):
            payload = {
                "contents": contents,
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "tools": GEMINI_TOOLS,
            }

            response = await self._call_gemini(api_key, payload)

            if response.status_code != 200:
                status = response.status_code
                try:
                    err_msg = response.json().get("error", {}).get("message", response.text[:200])
                except Exception:
                    err_msg = response.text[:200]
                if status in (401, 403):
                    return f"Error: Gemini API key rejected ({status}): {err_msg}"
                if status in (429, 503):
                    # Both models overloaded — fall back to mock agent silently
                    print(f"[GEMINI] Both models overloaded, falling back to mock agent")
                    return await self._run_mock_agent(self.state["history"][-1]["parts"][0]["text"])
                return f"Error: Gemini API returned {status}: {err_msg}"

            res_data = response.json()
            candidates = res_data.get("candidates", [])
            if not candidates:
                return "Gemini API did not return any candidates."

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            function_calls = [p.get("functionCall") for p in parts if p.get("functionCall")]

            if not function_calls:
                text_response = "".join(p.get("text", "") for p in parts)
                self.state["history"].append(content)
                return text_response

            self.state["history"].append(content)
            tool_content = {"role": "function", "parts": []}
            round_suggestions: List[Dict] = []

            for call in function_calls:
                name = call.get("name")
                call_args = call.get("args", {})
                tool_result = await execute_tool(
                    name,
                    call_args,
                    self.state,
                    aviasales=self.aviasales,
                    booking=self.booking,
                    china_train=self.china_train,
                )
                tool_content["parts"].append({
                    "functionResponse": {"name": name, "response": tool_result}
                })
                round_suggestions += self._suggestions_from_tool(name, tool_result)

            if round_suggestions:
                self.state["_last_suggestions"] = round_suggestions

            self.state["history"].append(tool_content)
            contents = self.state["history"]

        return "Max iterations reached without a final response from the agent."
