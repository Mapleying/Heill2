import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# Mock Sports Camps database
MOCK_CAMPS = [
    {
        "camp_id": "tennis-lamanga",
        "name": "La Manga Club Tennis Camp",
        "sport": "tennis",
        "camp_type": "residential",
        "operator_name": "La Manga Tennis Ltd",
        "operator_verified": True,
        "location": {
            "address": "La Manga Club, 30389 Carretera de Atamaría",
            "city": "Murcia",
            "country_code": "ES",
            "lat": 37.6047,
            "lng": -0.8021
        },
        "skill_level_min": "ntrp_3.0",
        "skill_level_max": "ntrp_6.0",
        "max_group_size": 6,
        "solo_friendly": True,
        "language_of_instruction": ["English", "Spanish"],
        "amenities": ["tennis_courts", "gym", "pool", "early_breakfast", "spa"],
        "cancellation_policy": "Moderate (14 days free cancellation)",
        "source": "partner_api",
        "average_review_score": 4.8,
        "review_count": 142,
        "sessions": [
            {"session_id": "session-tennis-lamanga-1", "start_date": "2026-07-05", "end_date": "2026-07-11", "capacity": 12, "spots_remaining": 4, "price_per_person_eur": 1200.0},
            {"session_id": "session-tennis-lamanga-2", "start_date": "2026-07-19", "end_date": "2026-07-25", "capacity": 12, "spots_remaining": 6, "price_per_person_eur": 1250.0},
            {"session_id": "session-tennis-lamanga-3", "start_date": "2026-08-02", "end_date": "2026-08-08", "capacity": 12, "spots_remaining": 0, "price_per_person_eur": 1300.0}
        ]
    },
    {
        "camp_id": "tennis-nadal",
        "name": "Rafa Nadal Academy Elite Camp",
        "sport": "tennis",
        "camp_type": "residential",
        "operator_name": "RNA Group",
        "operator_verified": True,
        "location": {
            "address": "Ctra. Cales de Mallorca s/n, km 1.2",
            "city": "Manacor, Mallorca",
            "country_code": "ES",
            "lat": 39.5772,
            "lng": 3.2208
        },
        "skill_level_min": "ntrp_3.5",
        "skill_level_max": "ntrp_7.0",
        "max_group_size": 4,
        "solo_friendly": True,
        "language_of_instruction": ["English", "Spanish", "French"],
        "amenities": ["tennis_courts", "gym", "pool", "early_breakfast", "restaurant", "physio"],
        "cancellation_policy": "Strict (No refund within 30 days)",
        "source": "partner_api",
        "average_review_score": 4.9,
        "review_count": 289,
        "sessions": [
            {"session_id": "session-tennis-nadal-1", "start_date": "2026-07-12", "end_date": "2026-07-18", "capacity": 20, "spots_remaining": 2, "price_per_person_eur": 2100.0},
            {"session_id": "session-tennis-nadal-2", "start_date": "2026-08-09", "end_date": "2026-08-15", "capacity": 20, "spots_remaining": 8, "price_per_person_eur": 2200.0}
        ]
    },
    {
        "camp_id": "ski-chamonix",
        "name": "Chamonix Off-Piste freeride Camp",
        "sport": "skiing",
        "camp_type": "clinic",
        "operator_name": "Chamonix Mountain Guides",
        "operator_verified": True,
        "location": {
            "address": "190 Place de l'Eglise",
            "city": "Chamonix-Mont-Blanc",
            "country_code": "FR",
            "lat": 45.9227,
            "lng": 6.8685
        },
        "skill_level_min": "ski_intermediate",
        "skill_level_max": "ski_expert",
        "max_group_size": 5,
        "solo_friendly": True,
        "language_of_instruction": ["English", "French"],
        "amenities": ["ski_storage", "early_breakfast", "sauna"],
        "cancellation_policy": "Flexible (48h free cancellation)",
        "source": "internal",
        "average_review_score": 4.7,
        "review_count": 94,
        "sessions": [
            {"session_id": "session-ski-chamonix-1", "start_date": "2027-01-10", "end_date": "2027-01-16", "capacity": 10, "spots_remaining": 3, "price_per_person_eur": 950.0},
            {"session_id": "session-ski-chamonix-2", "start_date": "2027-02-07", "end_date": "2027-02-13", "capacity": 10, "spots_remaining": 5, "price_per_person_eur": 1100.0}
        ]
    },
    {
        "camp_id": "ski-valthorens",
        "name": "Val Thorens Altitude Ski Academy",
        "sport": "skiing",
        "camp_type": "residential",
        "operator_name": "ESF Val Thorens",
        "operator_verified": True,
        "location": {
            "address": "Maison de Val Thorens",
            "city": "Val Thorens",
            "country_code": "FR",
            "lat": 45.2982,
            "lng": 6.5800
        },
        "skill_level_min": "ski_beginner",
        "skill_level_max": "ski_advanced",
        "max_group_size": 8,
        "solo_friendly": False,
        "language_of_instruction": ["English", "French", "German"],
        "amenities": ["ski_storage", "pool", "early_breakfast", "ski_in_ski_out"],
        "cancellation_policy": "Moderate (14 days free cancellation)",
        "source": "scraped",
        "average_review_score": 4.6,
        "review_count": 112,
        "sessions": [
            {"session_id": "session-ski-valthorens-1", "start_date": "2027-01-17", "end_date": "2027-01-23", "capacity": 16, "spots_remaining": 7, "price_per_person_eur": 850.0},
            {"session_id": "session-ski-valthorens-2", "start_date": "2027-02-14", "end_date": "2027-02-20", "capacity": 16, "spots_remaining": 12, "price_per_person_eur": 900.0}
        ]
    },
    {
        "camp_id": "surf-ericeira",
        "name": "Ericeira Surf Camp & Yoga Retreat",
        "sport": "surfing",
        "camp_type": "residential",
        "operator_name": "Ericeira Waves Group",
        "operator_verified": True,
        "location": {
            "address": "Rua dos Surfistas, No. 5",
            "city": "Ericeira",
            "country_code": "PT",
            "lat": 38.9634,
            "lng": -9.4124
        },
        "skill_level_min": "surf_beginner",
        "skill_level_max": "surf_intermediate",
        "max_group_size": 6,
        "solo_friendly": True,
        "language_of_instruction": ["English", "Portuguese", "German"],
        "amenities": ["surf_rinse_station", "yoga_deck", "pool", "early_breakfast", "surfboard_rental"],
        "cancellation_policy": "Flexible (7 days free cancellation)",
        "source": "partner_api",
        "average_review_score": 4.9,
        "review_count": 320,
        "sessions": [
            {"session_id": "session-surf-ericeira-1", "start_date": "2026-07-12", "end_date": "2026-07-18", "capacity": 15, "spots_remaining": 5, "price_per_person_eur": 750.0},
            {"session_id": "session-surf-ericeira-2", "start_date": "2026-08-02", "end_date": "2026-08-08", "capacity": 15, "spots_remaining": 2, "price_per_person_eur": 800.0},
            {"session_id": "session-surf-ericeira-3", "start_date": "2026-09-13", "end_date": "2026-09-19", "capacity": 15, "spots_remaining": 9, "price_per_person_eur": 700.0}
        ]
    },
    {
        "camp_id": "surf-hossegor",
        "name": "Hossegor Performance Surf Center",
        "sport": "surfing",
        "camp_type": "clinic",
        "operator_name": "Landes Surf Academy",
        "operator_verified": True,
        "location": {
            "address": "Plage des Estagnots",
            "city": "Hossegor",
            "country_code": "FR",
            "lat": 43.6841,
            "lng": -1.4325
        },
        "skill_level_min": "surf_intermediate",
        "skill_level_max": "surf_advanced",
        "max_group_size": 4,
        "solo_friendly": True,
        "language_of_instruction": ["English", "French"],
        "amenities": ["surf_rinse_station", "video_analysis", "gym"],
        "cancellation_policy": "Strict (No refund within 14 days)",
        "source": "internal",
        "average_review_score": 4.8,
        "review_count": 86,
        "sessions": [
            {"session_id": "session-surf-hossegor-1", "start_date": "2026-07-19", "end_date": "2026-07-25", "capacity": 8, "spots_remaining": 3, "price_per_person_eur": 990.0},
            {"session_id": "session-surf-hossegor-2", "start_date": "2026-08-23", "end_date": "2026-08-29", "capacity": 8, "spots_remaining": 4, "price_per_person_eur": 1050.0}
        ]
    }
]

# Airport mapping near camps
AIRPORT_MAPPING = {
    "Murcia": [
        {"iata": "RMU", "name": "Murcia International Airport", "transfer_time_mins": 30},
        {"iata": "ALC", "name": "Alicante-Elche Airport", "transfer_time_mins": 75}
    ],
    "Manacor, Mallorca": [
        {"iata": "PMI", "name": "Palma de Mallorca Airport", "transfer_time_mins": 45}
    ],
    "Chamonix-Mont-Blanc": [
        {"iata": "GVA", "name": "Geneva Airport", "transfer_time_mins": 75},
        {"iata": "LYS", "name": "Lyon-Saint Exupéry Airport", "transfer_time_mins": 140}
    ],
    "Val Thorens": [
        {"iata": "GVA", "name": "Geneva Airport", "transfer_time_mins": 150},
        {"iata": "LYS", "name": "Lyon-Saint Exupéry Airport", "transfer_time_mins": 150},
        {"iata": "CMF", "name": "Chambéry-Savoie Airport", "transfer_time_mins": 90}
    ],
    "Ericeira": [
        {"iata": "LIS", "name": "Humberto Delgado Airport (Lisbon)", "transfer_time_mins": 40}
    ],
    "Hossegor": [
        {"iata": "BIQ", "name": "Biarritz Pays Basque Airport", "transfer_time_mins": 35},
        {"iata": "BOD", "name": "Bordeaux-Mérignac Airport", "transfer_time_mins": 110}
    ]
}

# Mock Hotels Database
MOCK_HOTELS = [
    {
        "hotel_id": "hotel-lamanga-resort",
        "name": "Grand Hyatt La Manga Club Golf & Spa",
        "lat": 37.6041,
        "lng": -0.8030,
        "stars": 5,
        "amenities": ["tennis_courts", "pool", "gym", "early_breakfast", "spa"],
        "price_per_night_eur": 210.0,
        "booking_link": "https://www.booking.com/hotel/es/grand-hyatt-la-manga-club.html",
        "sport_partner": True
    },
    {
        "hotel_id": "hotel-lamanga-apartments",
        "name": "Las Lomas Village - La Manga Club",
        "lat": 37.6090,
        "lng": -0.8010,
        "stars": 4,
        "amenities": ["pool", "early_breakfast", "tennis_courts"],
        "price_per_night_eur": 125.0,
        "booking_link": "https://www.booking.com/hotel/es/las-lomas-village.html",
        "sport_partner": True
    },
    {
        "hotel_id": "hotel-manacor-rural",
        "name": "La Reserva Rotana Mallorca",
        "lat": 39.5910,
        "lng": 3.2050,
        "stars": 4,
        "amenities": ["tennis_courts", "pool", "early_breakfast"],
        "price_per_night_eur": 180.0,
        "booking_link": "https://www.booking.com/hotel/es/la-reserva-rotana.html",
        "sport_partner": False
    },
    {
        "hotel_id": "hotel-chamonix-alpina",
        "name": "Alpina Eclectic Hotel",
        "lat": 45.9242,
        "lng": 6.8700,
        "stars": 4,
        "amenities": ["ski_storage", "early_breakfast", "sauna"],
        "price_per_night_eur": 140.0,
        "booking_link": "https://www.booking.com/hotel/fr/alpina-chamonix.html",
        "sport_partner": True
    },
    {
        "hotel_id": "hotel-chamonix-hostel",
        "name": "Chamonix Lodge",
        "lat": 45.9170,
        "lng": 6.8590,
        "stars": 2,
        "amenities": ["ski_storage", "early_breakfast"],
        "price_per_night_eur": 55.0,
        "booking_link": "https://www.booking.com/hotel/fr/chamonix-lodge.html",
        "sport_partner": False
    },
    {
        "hotel_id": "hotel-valthorens-fits",
        "name": "Hotel Fitz Roy",
        "lat": 45.2980,
        "lng": 6.5795,
        "stars": 5,
        "amenities": ["ski_storage", "ski_in_ski_out", "early_breakfast", "pool"],
        "price_per_night_eur": 320.0,
        "booking_link": "https://www.booking.com/hotel/fr/le-fitz-roy.html",
        "sport_partner": True
    },
    {
        "hotel_id": "hotel-ericeira-villa",
        "name": "Ericeira Soul Guesthouse",
        "lat": 38.9628,
        "lng": -9.4140,
        "stars": 3,
        "amenities": ["surf_rinse_station", "early_breakfast", "pool"],
        "price_per_night_eur": 85.0,
        "booking_link": "https://www.booking.com/hotel/pt/ericeira-soul-guesthouse.html",
        "sport_partner": True
    },
    {
        "hotel_id": "hotel-ericeira-selina",
        "name": "Selina Boavista Ericeira",
        "lat": 38.9660,
        "lng": -9.4105,
        "stars": 3,
        "amenities": ["surf_rinse_station", "pool", "surfboard_rental"],
        "price_per_night_eur": 70.0,
        "booking_link": "https://www.booking.com/hotel/pt/selina-ericeira.html",
        "sport_partner": False
    },
    {
        "hotel_id": "hotel-hossegor-lesort",
        "name": "Les Hortensias du Lac",
        "lat": 43.6795,
        "lng": -1.4340,
        "stars": 4,
        "amenities": ["surf_rinse_station", "pool", "early_breakfast", "spa"],
        "price_per_night_eur": 190.0,
        "booking_link": "https://www.booking.com/hotel/fr/les-hortensias-du-lac.html",
        "sport_partner": True
    }
]

# Helper search functions
# Country name → ISO code mapping for location filtering
_COUNTRY_ALIASES: Dict[str, str] = {
    "spain": "es", "españa": "es",
    "france": "fr", "french": "fr",
    "portugal": "pt", "portuguese": "pt",
    "uk": "gb", "england": "gb", "britain": "gb",
    "germany": "de", "italy": "it",
}


def search_camps(sport: Optional[str] = None, skill_level: Optional[str] = None, location: Optional[str] = None) -> List[Dict[str, Any]]:
    results = []
    for camp in MOCK_CAMPS:
        if sport and camp["sport"].lower() != sport.lower():
            continue

        if location:
            loc = location.lower().strip()
            # Resolve country name → ISO code so "spain" matches "ES"
            loc_code = _COUNTRY_ALIASES.get(loc, loc)
            city    = camp["location"]["city"].lower()
            cc      = camp["location"]["country_code"].lower()
            if loc not in city and loc_code not in city and loc not in cc and loc_code not in cc:
                continue

        if skill_level:
            min_l = camp["skill_level_min"]
            if "ntrp" in skill_level and "ntrp" not in min_l:
                continue
            if "ski" in skill_level and "ski" not in min_l:
                continue
            if "surf" in skill_level and "surf" not in min_l:
                continue

        results.append(camp)
    return results

def get_camp_details(camp_id: str) -> Optional[Dict[str, Any]]:
    for camp in MOCK_CAMPS:
        if camp["camp_id"] == camp_id:
            return camp
    return None

def get_camp_coordinates_by_city(city: str) -> Optional[tuple]:
    """Return (lat, lng) for the first camp whose city matches the given string."""
    for camp in MOCK_CAMPS:
        if city.lower() in camp["location"]["city"].lower():
            return camp["location"]["lat"], camp["location"]["lng"]
    return None

def get_airports_for_camp(city: str) -> List[Dict[str, Any]]:
    # Find matching key by substring
    for key, airports in AIRPORT_MAPPING.items():
        if city.lower() in key.lower() or key.lower() in city.lower():
            return airports
    return []

def search_flights_mock(origin: str, destination_city: str, date: str, equipment_type: Optional[str] = None) -> List[Dict[str, Any]]:
    # Mock flight offers
    airports = get_airports_for_camp(destination_city)
    if not airports:
        return []
    
    # Generate mock flights for each destination airport
    flights = []
    airlines = ["Iberia", "Air France", "TAP Portugal", "Lufthansa", "EasyJet", "Ryanair"]
    
    # Equip fee estimates
    equip_fee = 0.0
    if equipment_type:
        if equipment_type.lower() in ["skis", "snowboard"]:
            equip_fee = 50.0
        elif equipment_type.lower() == "surfboard":
            equip_fee = 70.0
    
    for i, ap in enumerate(airports):
        # Generate 2 flights per airport
        dest_iata = ap["iata"]
        
        # Flight 1: Direct, standard airline
        flights.append({
            "flight_id": f"flight-{origin.lower()}-{dest_iata.lower()}-1",
            "airline": airlines[i % len(airlines)],
            "origin": origin.upper(),
            "destination": dest_iata,
            "departure_time": f"{date} 08:30",
            "arrival_time": f"{date} 11:45",
            "stops": 0,
            "price_eur": 180.0 + (i * 30),
            "baggage_allowance": "1 Checked bag (23kg)",
            "equipment_fee_eur": equip_fee,
            "booking_link": f"https://www.amadeus.com/flights?from={origin}&to={dest_iata}&date={date}"
        })
        
        # Flight 2: 1 Stop, budget airline
        flights.append({
            "flight_id": f"flight-{origin.lower()}-{dest_iata.lower()}-2",
            "airline": airlines[(i + 1) % len(airlines)],
            "origin": origin.upper(),
            "destination": dest_iata,
            "departure_time": f"{date} 14:15",
            "arrival_time": f"{date} 19:30",
            "stops": 1,
            "price_eur": 95.0 + (i * 15),
            "baggage_allowance": "Cabin bag only",
            "equipment_fee_eur": equip_fee + 15, # budget airline surcharges
            "booking_link": f"https://www.skyscanner.com/transport/flights/{origin}/{dest_iata}/{date}"
        })
        
    return flights

def search_hotels_mock(camp_lat: float, camp_lng: float, city: str, amenities: List[str] = None) -> List[Dict[str, Any]]:
    # Find hotels near the city or lat/lng
    results = []
    for hotel in MOCK_HOTELS:
        # Match if hotel amenities contain requested or if hotel is close to the city
        # For simplicity, filter by city coordinate approximation or just list matches
        # If specific amenities are requested:
        if amenities:
            # Check if all requested amenities are present in hotel amenities
            # To be more forgiving, we score them and sort or filter
            if not any(a in hotel["amenities"] for a in amenities):
                continue
        results.append(hotel)
    
    # Sort results so sport_partner is first
    results.sort(key=lambda x: (not x["sport_partner"], x["price_per_night_eur"]))
    return results
