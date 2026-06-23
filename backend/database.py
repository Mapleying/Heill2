import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# ── Supabase client (lazy init) ───────────────────────────────────────────────

_sb = None

def _client():
    global _sb
    if _sb is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if url and key:
            from supabase import create_client
            _sb = create_client(url, key)
    return _sb

# ── Row → nested dict helpers ─────────────────────────────────────────────────

def _to_camp(row: Dict, sessions: List[Dict]) -> Dict:
    return {
        "camp_id": row["camp_id"],
        "name": row["name"],
        "sport": row["sport"],
        "camp_type": row.get("camp_type"),
        "operator_name": row.get("operator_name"),
        "operator_verified": row.get("operator_verified", False),
        "location": {
            "address": row.get("address", ""),
            "city": row.get("city", ""),
            "country_code": row.get("country_code", ""),
            "lat": row.get("lat", 0),
            "lng": row.get("lng", 0),
        },
        "skill_level_min": row.get("skill_level_min"),
        "skill_level_max": row.get("skill_level_max"),
        "max_group_size": row.get("max_group_size"),
        "solo_friendly": row.get("solo_friendly", True),
        "language_of_instruction": row.get("language_of_instruction") or [],
        "amenities": row.get("amenities") or [],
        "cancellation_policy": row.get("cancellation_policy"),
        "source": row.get("source"),
        "average_review_score": row.get("average_review_score", 0),
        "review_count": row.get("review_count", 0),
        "sessions": sessions,
    }

def _to_session(row: Dict) -> Dict:
    return {
        "session_id": row["session_id"],
        "start_date": str(row["start_date"]),
        "end_date": str(row["end_date"]),
        "capacity": row.get("capacity", 0),
        "spots_remaining": row.get("spots_remaining", 0),
        "price_per_person_eur": row.get("price_per_person_eur", 0),
    }

# ── Public API ────────────────────────────────────────────────────────────────

_COUNTRY_ALIASES: Dict[str, str] = {
    "spain": "es", "españa": "es",
    "france": "fr", "french": "fr",
    "portugal": "pt", "portuguese": "pt",
    "uk": "gb", "england": "gb", "britain": "gb",
    "germany": "de", "italy": "it",
}


def search_camps(sport: Optional[str] = None, skill_level: Optional[str] = None, location: Optional[str] = None) -> List[Dict[str, Any]]:
    sb = _client()
    if not sb:
        return _search_camps_mock(sport, skill_level, location)

    q = sb.table("camps").select("*")
    if sport:
        q = q.eq("sport", sport.lower())
    if location:
        loc = location.lower().strip()
        loc_code = _COUNTRY_ALIASES.get(loc, loc)
        q = q.or_(f"city.ilike.%{loc}%,city.ilike.%{loc_code}%,country_code.ilike.%{loc}%,country_code.ilike.%{loc_code}%")

    camps = (q.execute().data or [])
    if not camps:
        return []

    # Fetch all sessions for these camps in one query
    camp_ids = [c["camp_id"] for c in camps]
    sessions_rows = sb.table("camp_sessions").select("*").in_("camp_id", camp_ids).execute().data or []

    sessions_by_camp: Dict[str, List] = {}
    for s in sessions_rows:
        sessions_by_camp.setdefault(s["camp_id"], []).append(_to_session(s))

    result = [_to_camp(c, sessions_by_camp.get(c["camp_id"], [])) for c in camps]

    # Apply skill_level filter in Python (same logic as mock)
    if skill_level:
        result = [
            c for c in result
            if (
                ("ntrp" in skill_level and "ntrp" in (c["skill_level_min"] or "")) or
                ("ski_" in skill_level and "ski_" in (c["skill_level_min"] or "")) or
                ("surf_" in skill_level and "surf_" in (c["skill_level_min"] or ""))
            )
        ]
    return result


def get_camp_details(camp_id: str) -> Optional[Dict[str, Any]]:
    sb = _client()
    if not sb:
        return _get_camp_details_mock(camp_id)

    res = sb.table("camps").select("*").eq("camp_id", camp_id).execute()
    if not res.data:
        return None

    sessions_rows = sb.table("camp_sessions").select("*").eq("camp_id", camp_id).execute().data or []
    return _to_camp(res.data[0], [_to_session(s) for s in sessions_rows])


def get_airports_for_camp(city: str) -> List[Dict[str, Any]]:
    sb = _client()
    if not sb:
        return _get_airports_for_camp_mock(city)

    res = sb.table("airport_mapping").select("*").ilike("city", f"%{city}%").execute()
    rows = res.data or []
    if not rows:
        # try reverse substring
        all_rows = sb.table("airport_mapping").select("*").execute().data or []
        rows = [r for r in all_rows if city.lower() in r["city"].lower() or r["city"].lower() in city.lower()]

    return [{"iata": r["iata"], "name": r["name"], "transfer_time_mins": r["transfer_time_mins"]} for r in rows]


def get_camp_coordinates_by_city(city: str) -> Optional[tuple]:
    sb = _client()
    if not sb:
        return _get_camp_coordinates_by_city_mock(city)

    res = sb.table("camps").select("lat,lng,city").ilike("city", f"%{city}%").limit(1).execute()
    if res.data:
        return res.data[0]["lat"], res.data[0]["lng"]
    return None


def search_hotels_mock(camp_lat: float, camp_lng: float, city: str, amenities: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    sb = _client()
    if not sb:
        return _search_hotels_mock_data(camp_lat, camp_lng, city, amenities)

    q = sb.table("hotels").select("*")
    if city:
        q = q.ilike("city", f"%{city}%")

    hotels = q.execute().data or []

    if amenities:
        hotels = [h for h in hotels if any(a in (h.get("amenities") or []) for a in amenities)]

    hotels.sort(key=lambda h: (not h.get("sport_partner", False), h.get("price_per_night_eur", 0)))
    return hotels


# ── Flights stay mock (real data comes from Aviasales client) ─────────────────

def search_flights_mock(origin: str, destination_city: str, date: str, equipment_type: Optional[str] = None) -> List[Dict[str, Any]]:
    airports = get_airports_for_camp(destination_city)
    if not airports:
        return []

    equip_fee = 0.0
    if equipment_type:
        if equipment_type.lower() in ["skis", "snowboard"]:
            equip_fee = 50.0
        elif equipment_type.lower() == "surfboard":
            equip_fee = 70.0

    airlines = ["Iberia", "Air France", "TAP Portugal", "Lufthansa", "EasyJet", "Ryanair"]
    flights = []
    for i, ap in enumerate(airports):
        dest = ap["iata"]
        flights.append({
            "flight_id": f"flight-{origin.lower()}-{dest.lower()}-1",
            "airline": airlines[i % len(airlines)],
            "origin": origin.upper(), "destination": dest,
            "departure_time": f"{date} 08:30", "arrival_time": f"{date} 11:45",
            "stops": 0, "price_eur": 180.0 + i * 30,
            "baggage_allowance": "1 Checked bag (23kg)",
            "equipment_fee_eur": equip_fee,
            "booking_link": f"https://www.amadeus.com/flights?from={origin}&to={dest}&date={date}",
        })
        flights.append({
            "flight_id": f"flight-{origin.lower()}-{dest.lower()}-2",
            "airline": airlines[(i + 1) % len(airlines)],
            "origin": origin.upper(), "destination": dest,
            "departure_time": f"{date} 14:15", "arrival_time": f"{date} 19:30",
            "stops": 1, "price_eur": 95.0 + i * 15,
            "baggage_allowance": "Cabin bag only",
            "equipment_fee_eur": equip_fee + 15,
            "booking_link": f"https://www.skyscanner.com/transport/flights/{origin}/{dest}/{date}",
        })
    return flights


# ── In-memory mock fallbacks (used when Supabase is not configured) ───────────

MOCK_CAMPS = [
    {"camp_id":"tennis-lamanga","name":"La Manga Club Tennis Camp","sport":"tennis","camp_type":"residential","operator_name":"La Manga Tennis Ltd","operator_verified":True,"location":{"address":"La Manga Club, 30389 Carretera de Atamaría","city":"Murcia","country_code":"ES","lat":37.6047,"lng":-0.8021},"skill_level_min":"ntrp_3.0","skill_level_max":"ntrp_6.0","max_group_size":6,"solo_friendly":True,"language_of_instruction":["English","Spanish"],"amenities":["tennis_courts","gym","pool","early_breakfast","spa"],"cancellation_policy":"Moderate (14 days free cancellation)","source":"partner_api","average_review_score":4.8,"review_count":142,"sessions":[{"session_id":"session-tennis-lamanga-1","start_date":"2026-07-05","end_date":"2026-07-11","capacity":12,"spots_remaining":4,"price_per_person_eur":1200.0},{"session_id":"session-tennis-lamanga-2","start_date":"2026-07-19","end_date":"2026-07-25","capacity":12,"spots_remaining":6,"price_per_person_eur":1250.0},{"session_id":"session-tennis-lamanga-3","start_date":"2026-08-02","end_date":"2026-08-08","capacity":12,"spots_remaining":0,"price_per_person_eur":1300.0}]},
    {"camp_id":"tennis-nadal","name":"Rafa Nadal Academy Elite Camp","sport":"tennis","camp_type":"residential","operator_name":"RNA Group","operator_verified":True,"location":{"address":"Ctra. Cales de Mallorca s/n, km 1.2","city":"Manacor, Mallorca","country_code":"ES","lat":39.5772,"lng":3.2208},"skill_level_min":"ntrp_3.5","skill_level_max":"ntrp_7.0","max_group_size":4,"solo_friendly":True,"language_of_instruction":["English","Spanish","French"],"amenities":["tennis_courts","gym","pool","early_breakfast","restaurant","physio"],"cancellation_policy":"Strict (No refund within 30 days)","source":"partner_api","average_review_score":4.9,"review_count":289,"sessions":[{"session_id":"session-tennis-nadal-1","start_date":"2026-07-12","end_date":"2026-07-18","capacity":20,"spots_remaining":2,"price_per_person_eur":2100.0},{"session_id":"session-tennis-nadal-2","start_date":"2026-08-09","end_date":"2026-08-15","capacity":20,"spots_remaining":8,"price_per_person_eur":2200.0}]},
    {"camp_id":"ski-chamonix","name":"Chamonix Off-Piste Freeride Camp","sport":"skiing","camp_type":"clinic","operator_name":"Chamonix Mountain Guides","operator_verified":True,"location":{"address":"190 Place de l'Eglise","city":"Chamonix-Mont-Blanc","country_code":"FR","lat":45.9227,"lng":6.8685},"skill_level_min":"ski_intermediate","skill_level_max":"ski_expert","max_group_size":5,"solo_friendly":True,"language_of_instruction":["English","French"],"amenities":["ski_storage","early_breakfast","sauna"],"cancellation_policy":"Flexible (48h free cancellation)","source":"internal","average_review_score":4.7,"review_count":94,"sessions":[{"session_id":"session-ski-chamonix-1","start_date":"2027-01-10","end_date":"2027-01-16","capacity":10,"spots_remaining":3,"price_per_person_eur":950.0},{"session_id":"session-ski-chamonix-2","start_date":"2027-02-07","end_date":"2027-02-13","capacity":10,"spots_remaining":5,"price_per_person_eur":1100.0}]},
    {"camp_id":"ski-valthorens","name":"Val Thorens Altitude Ski Academy","sport":"skiing","camp_type":"residential","operator_name":"ESF Val Thorens","operator_verified":True,"location":{"address":"Maison de Val Thorens","city":"Val Thorens","country_code":"FR","lat":45.2982,"lng":6.5800},"skill_level_min":"ski_beginner","skill_level_max":"ski_advanced","max_group_size":8,"solo_friendly":False,"language_of_instruction":["English","French","German"],"amenities":["ski_storage","pool","early_breakfast","ski_in_ski_out"],"cancellation_policy":"Moderate (14 days free cancellation)","source":"scraped","average_review_score":4.6,"review_count":112,"sessions":[{"session_id":"session-ski-valthorens-1","start_date":"2027-01-17","end_date":"2027-01-23","capacity":16,"spots_remaining":7,"price_per_person_eur":850.0},{"session_id":"session-ski-valthorens-2","start_date":"2027-02-14","end_date":"2027-02-20","capacity":16,"spots_remaining":12,"price_per_person_eur":900.0}]},
    {"camp_id":"surf-ericeira","name":"Ericeira Surf Camp & Yoga Retreat","sport":"surfing","camp_type":"residential","operator_name":"Ericeira Waves Group","operator_verified":True,"location":{"address":"Rua dos Surfistas, No. 5","city":"Ericeira","country_code":"PT","lat":38.9634,"lng":-9.4124},"skill_level_min":"surf_beginner","skill_level_max":"surf_intermediate","max_group_size":6,"solo_friendly":True,"language_of_instruction":["English","Portuguese","German"],"amenities":["surf_rinse_station","yoga_deck","pool","early_breakfast","surfboard_rental"],"cancellation_policy":"Flexible (7 days free cancellation)","source":"partner_api","average_review_score":4.9,"review_count":320,"sessions":[{"session_id":"session-surf-ericeira-1","start_date":"2026-07-12","end_date":"2026-07-18","capacity":15,"spots_remaining":5,"price_per_person_eur":750.0},{"session_id":"session-surf-ericeira-2","start_date":"2026-08-02","end_date":"2026-08-08","capacity":15,"spots_remaining":2,"price_per_person_eur":800.0},{"session_id":"session-surf-ericeira-3","start_date":"2026-09-13","end_date":"2026-09-19","capacity":15,"spots_remaining":9,"price_per_person_eur":700.0}]},
    {"camp_id":"surf-hossegor","name":"Hossegor Performance Surf Center","sport":"surfing","camp_type":"clinic","operator_name":"Landes Surf Academy","operator_verified":True,"location":{"address":"Plage des Estagnots","city":"Hossegor","country_code":"FR","lat":43.6841,"lng":-1.4325},"skill_level_min":"surf_intermediate","skill_level_max":"surf_advanced","max_group_size":4,"solo_friendly":True,"language_of_instruction":["English","French"],"amenities":["surf_rinse_station","video_analysis","gym"],"cancellation_policy":"Strict (No refund within 14 days)","source":"internal","average_review_score":4.8,"review_count":86,"sessions":[{"session_id":"session-surf-hossegor-1","start_date":"2026-07-19","end_date":"2026-07-25","capacity":8,"spots_remaining":3,"price_per_person_eur":990.0},{"session_id":"session-surf-hossegor-2","start_date":"2026-08-23","end_date":"2026-08-29","capacity":8,"spots_remaining":4,"price_per_person_eur":1050.0}]},
]

MOCK_HOTELS = [
    {"hotel_id":"hotel-lamanga-resort","name":"Grand Hyatt La Manga Club Golf & Spa","city":"Murcia","lat":37.6041,"lng":-0.8030,"stars":5,"amenities":["tennis_courts","pool","gym","early_breakfast","spa"],"price_per_night_eur":210.0,"booking_link":"https://www.booking.com/hotel/es/grand-hyatt-la-manga-club.html","sport_partner":True},
    {"hotel_id":"hotel-lamanga-apartments","name":"Las Lomas Village - La Manga Club","city":"Murcia","lat":37.6090,"lng":-0.8010,"stars":4,"amenities":["pool","early_breakfast","tennis_courts"],"price_per_night_eur":125.0,"booking_link":"https://www.booking.com/hotel/es/las-lomas-village.html","sport_partner":True},
    {"hotel_id":"hotel-manacor-rural","name":"La Reserva Rotana Mallorca","city":"Manacor, Mallorca","lat":39.5910,"lng":3.2050,"stars":4,"amenities":["tennis_courts","pool","early_breakfast"],"price_per_night_eur":180.0,"booking_link":"https://www.booking.com/hotel/es/la-reserva-rotana.html","sport_partner":False},
    {"hotel_id":"hotel-chamonix-alpina","name":"Alpina Eclectic Hotel","city":"Chamonix-Mont-Blanc","lat":45.9242,"lng":6.8700,"stars":4,"amenities":["ski_storage","early_breakfast","sauna"],"price_per_night_eur":140.0,"booking_link":"https://www.booking.com/hotel/fr/alpina-chamonix.html","sport_partner":True},
    {"hotel_id":"hotel-chamonix-hostel","name":"Chamonix Lodge","city":"Chamonix-Mont-Blanc","lat":45.9170,"lng":6.8590,"stars":2,"amenities":["ski_storage","early_breakfast"],"price_per_night_eur":55.0,"booking_link":"https://www.booking.com/hotel/fr/chamonix-lodge.html","sport_partner":False},
    {"hotel_id":"hotel-valthorens-fits","name":"Hotel Fitz Roy","city":"Val Thorens","lat":45.2980,"lng":6.5795,"stars":5,"amenities":["ski_storage","ski_in_ski_out","early_breakfast","pool"],"price_per_night_eur":320.0,"booking_link":"https://www.booking.com/hotel/fr/le-fitz-roy.html","sport_partner":True},
    {"hotel_id":"hotel-ericeira-villa","name":"Ericeira Soul Guesthouse","city":"Ericeira","lat":38.9628,"lng":-9.4140,"stars":3,"amenities":["surf_rinse_station","early_breakfast","pool"],"price_per_night_eur":85.0,"booking_link":"https://www.booking.com/hotel/pt/ericeira-soul-guesthouse.html","sport_partner":True},
    {"hotel_id":"hotel-ericeira-selina","name":"Selina Boavista Ericeira","city":"Ericeira","lat":38.9660,"lng":-9.4105,"stars":3,"amenities":["surf_rinse_station","pool","surfboard_rental"],"price_per_night_eur":70.0,"booking_link":"https://www.booking.com/hotel/pt/selina-ericeira.html","sport_partner":False},
    {"hotel_id":"hotel-hossegor-lesort","name":"Les Hortensias du Lac","city":"Hossegor","lat":43.6795,"lng":-1.4340,"stars":4,"amenities":["surf_rinse_station","pool","early_breakfast","spa"],"price_per_night_eur":190.0,"booking_link":"https://www.booking.com/hotel/fr/les-hortensias-du-lac.html","sport_partner":True},
]

AIRPORT_MAPPING = {
    "Murcia": [{"iata":"RMU","name":"Murcia International Airport","transfer_time_mins":30},{"iata":"ALC","name":"Alicante-Elche Airport","transfer_time_mins":75}],
    "Manacor, Mallorca": [{"iata":"PMI","name":"Palma de Mallorca Airport","transfer_time_mins":45}],
    "Chamonix-Mont-Blanc": [{"iata":"GVA","name":"Geneva Airport","transfer_time_mins":75},{"iata":"LYS","name":"Lyon-Saint Exupéry Airport","transfer_time_mins":140}],
    "Val Thorens": [{"iata":"GVA","name":"Geneva Airport","transfer_time_mins":150},{"iata":"LYS","name":"Lyon-Saint Exupéry Airport","transfer_time_mins":150},{"iata":"CMF","name":"Chambéry-Savoie Airport","transfer_time_mins":90}],
    "Ericeira": [{"iata":"LIS","name":"Humberto Delgado Airport (Lisbon)","transfer_time_mins":40}],
    "Hossegor": [{"iata":"BIQ","name":"Biarritz Pays Basque Airport","transfer_time_mins":35},{"iata":"BOD","name":"Bordeaux-Mérignac Airport","transfer_time_mins":110}],
}


def _search_camps_mock(sport=None, skill_level=None, location=None):
    results = []
    for camp in MOCK_CAMPS:
        if sport and camp["sport"].lower() != sport.lower():
            continue
        if location:
            loc = location.lower().strip()
            loc_code = _COUNTRY_ALIASES.get(loc, loc)
            city = camp["location"]["city"].lower()
            cc = camp["location"]["country_code"].lower()
            if loc not in city and loc_code not in city and loc not in cc and loc_code not in cc:
                continue
        if skill_level:
            min_l = camp["skill_level_min"]
            if "ntrp" in skill_level and "ntrp" not in min_l:
                continue
            if "ski_" in skill_level and "ski_" not in min_l:
                continue
            if "surf_" in skill_level and "surf_" not in min_l:
                continue
        results.append(camp)
    return results


def _get_camp_details_mock(camp_id: str):
    for c in MOCK_CAMPS:
        if c["camp_id"] == camp_id:
            return c
    return None


def _get_airports_for_camp_mock(city: str):
    for key, airports in AIRPORT_MAPPING.items():
        if city.lower() in key.lower() or key.lower() in city.lower():
            return airports
    return []


def _get_camp_coordinates_by_city_mock(city: str):
    for camp in MOCK_CAMPS:
        if city.lower() in camp["location"]["city"].lower():
            return camp["location"]["lat"], camp["location"]["lng"]
    return None


def _search_hotels_mock_data(camp_lat, camp_lng, city, amenities=None):
    results = [h for h in MOCK_HOTELS if not amenities or any(a in h["amenities"] for a in amenities)]
    results.sort(key=lambda h: (not h["sport_partner"], h["price_per_night_eur"]))
    return results


# ── China train data ──────────────────────────────────────────────────────────

CNY_TO_EUR = 1 / 7.85  # approximate exchange rate

CHINA_STATION_MAP: Dict[str, Dict] = {
    "beijing":   {"station": "Beijing South",      "code": "BJP", "lat": 39.8652, "lng": 116.3783},
    "shanghai":  {"station": "Shanghai Hongqiao",  "code": "SHH", "lat": 31.1977, "lng": 121.3287},
    "guangzhou": {"station": "Guangzhou South",    "code": "GZQ", "lat": 22.9064, "lng": 113.2654},
    "shenzhen":  {"station": "Shenzhen North",     "code": "IOQ", "lat": 22.6082, "lng": 114.0305},
    "chengdu":   {"station": "Chengdu East",       "code": "ICW", "lat": 30.6566, "lng": 104.1437},
    "chongqing": {"station": "Chongqing North",    "code": "CQW", "lat": 29.7280, "lng": 106.5510},
    "xian":      {"station": "Xi'an North",        "code": "IAO", "lat": 34.3792, "lng": 108.8388},
    "xi'an":     {"station": "Xi'an North",        "code": "IAO", "lat": 34.3792, "lng": 108.8388},
    "hangzhou":  {"station": "Hangzhou East",      "code": "HZH", "lat": 30.2936, "lng": 120.2150},
    "nanjing":   {"station": "Nanjing South",      "code": "NJH", "lat": 31.9627, "lng": 118.7968},
    "wuhan":     {"station": "Wuhan",              "code": "WHN", "lat": 30.5951, "lng": 114.2816},
    "tianjin":   {"station": "Tianjin South",      "code": "TJP", "lat": 39.0152, "lng": 117.0778},
    "changsha":  {"station": "Changsha South",     "code": "CSQ", "lat": 27.8564, "lng": 113.0194},
    "zhengzhou": {"station": "Zhengzhou East",     "code": "ZZH", "lat": 34.7614, "lng": 113.8564},
    "suzhou":    {"station": "Suzhou",             "code": "SZH", "lat": 31.2990, "lng": 120.6172},
    "qingdao":   {"station": "Qingdao North",      "code": "QDH", "lat": 36.2468, "lng": 120.4326},
    "jinan":     {"station": "Jinan West",         "code": "JNK", "lat": 36.6583, "lng": 116.8164},
    "hefei":     {"station": "Hefei South",        "code": "HFH", "lat": 31.7320, "lng": 117.2278},
    "nanchang":  {"station": "Nanchang West",      "code": "NCG", "lat": 28.6884, "lng": 115.8316},
    "fuzhou":    {"station": "Fuzhou",             "code": "FZS", "lat": 26.0816, "lng": 119.2824},
    "xiamen":    {"station": "Xiamen North",       "code": "XMH", "lat": 24.6490, "lng": 117.9860},
    "kunming":   {"station": "Kunming South",      "code": "KMQ", "lat": 24.8478, "lng": 102.7286},
    "guiyang":   {"station": "Guiyang North",      "code": "GIH", "lat": 26.6466, "lng": 106.7034},
    "nanning":   {"station": "Nanning East",       "code": "NNH", "lat": 22.8040, "lng": 108.3640},
    "harbin":    {"station": "Harbin West",        "code": "HBW", "lat": 45.7462, "lng": 126.6023},
    "shenyang":  {"station": "Shenyang North",     "code": "SYO", "lat": 41.8063, "lng": 123.4394},
    "dalian":    {"station": "Dalian North",       "code": "DLH", "lat": 38.9652, "lng": 121.6417},
}

# Pre-defined realistic routes: (origin_key, dest_key) → list of trains
# Prices in CNY; duration in minutes
_TRAIN_ROUTES: Dict[tuple, List[Dict]] = {
    ("beijing", "shanghai"): [
        {"number": "G1",   "type": "G", "dep": "07:00", "arr": "11:38", "dur": 278, "2nd": 553,  "1st": 933,  "biz": 1748},
        {"number": "G5",   "type": "G", "dep": "09:00", "arr": "13:48", "dur": 288, "2nd": 553,  "1st": 933,  "biz": 1748},
        {"number": "G13",  "type": "G", "dep": "13:05", "arr": "17:43", "dur": 278, "2nd": 553,  "1st": 933,  "biz": 1748},
        {"number": "G17",  "type": "G", "dep": "16:00", "arr": "20:38", "dur": 278, "2nd": 553,  "1st": 933,  "biz": 1748},
    ],
    ("shanghai", "beijing"): [
        {"number": "G2",   "type": "G", "dep": "07:00", "arr": "11:38", "dur": 278, "2nd": 553,  "1st": 933,  "biz": 1748},
        {"number": "G6",   "type": "G", "dep": "09:05", "arr": "13:48", "dur": 283, "2nd": 553,  "1st": 933,  "biz": 1748},
        {"number": "G14",  "type": "G", "dep": "12:55", "arr": "17:43", "dur": 288, "2nd": 553,  "1st": 933,  "biz": 1748},
    ],
    ("beijing", "guangzhou"): [
        {"number": "G71",  "type": "G", "dep": "08:00", "arr": "16:28", "dur": 508, "2nd": 865,  "1st": 1397, "biz": 2748},
        {"number": "G79",  "type": "G", "dep": "10:00", "arr": "18:28", "dur": 508, "2nd": 865,  "1st": 1397, "biz": 2748},
    ],
    ("guangzhou", "beijing"): [
        {"number": "G72",  "type": "G", "dep": "08:00", "arr": "16:28", "dur": 508, "2nd": 865,  "1st": 1397, "biz": 2748},
        {"number": "G80",  "type": "G", "dep": "12:00", "arr": "20:28", "dur": 508, "2nd": 865,  "1st": 1397, "biz": 2748},
    ],
    ("beijing", "xian"): [
        {"number": "G85",  "type": "G", "dep": "07:58", "arr": "12:25", "dur": 267, "2nd": 515,  "1st": 826,  "biz": 1654},
        {"number": "G87",  "type": "G", "dep": "09:00", "arr": "13:25", "dur": 265, "2nd": 515,  "1st": 826,  "biz": 1654},
        {"number": "G653", "type": "G", "dep": "15:30", "arr": "19:56", "dur": 266, "2nd": 515,  "1st": 826,  "biz": 1654},
    ],
    ("xian", "beijing"): [
        {"number": "G86",  "type": "G", "dep": "08:00", "arr": "12:25", "dur": 265, "2nd": 515,  "1st": 826,  "biz": 1654},
        {"number": "G654", "type": "G", "dep": "14:00", "arr": "18:25", "dur": 265, "2nd": 515,  "1st": 826,  "biz": 1654},
    ],
    ("xi'an", "beijing"): [
        {"number": "G86",  "type": "G", "dep": "08:00", "arr": "12:25", "dur": 265, "2nd": 515,  "1st": 826,  "biz": 1654},
        {"number": "G654", "type": "G", "dep": "14:00", "arr": "18:25", "dur": 265, "2nd": 515,  "1st": 826,  "biz": 1654},
    ],
    ("beijing", "xi'an"): [
        {"number": "G85",  "type": "G", "dep": "07:58", "arr": "12:25", "dur": 267, "2nd": 515,  "1st": 826,  "biz": 1654},
        {"number": "G87",  "type": "G", "dep": "09:00", "arr": "13:25", "dur": 265, "2nd": 515,  "1st": 826,  "biz": 1654},
    ],
    ("beijing", "wuhan"): [
        {"number": "G501", "type": "G", "dep": "08:06", "arr": "12:00", "dur": 234, "2nd": 465,  "1st": 745,  "biz": 1520},
        {"number": "G71",  "type": "G", "dep": "08:00", "arr": "11:58", "dur": 238, "2nd": 465,  "1st": 745,  "biz": 1520},
    ],
    ("wuhan", "beijing"): [
        {"number": "G502", "type": "G", "dep": "08:00", "arr": "12:00", "dur": 240, "2nd": 465,  "1st": 745,  "biz": 1520},
        {"number": "G72",  "type": "G", "dep": "13:00", "arr": "17:10", "dur": 250, "2nd": 465,  "1st": 745,  "biz": 1520},
    ],
    ("shanghai", "hangzhou"): [
        {"number": "G7301","type": "G", "dep": "07:00", "arr": "08:02", "dur": 62,  "2nd": 73,   "1st": 116,  "biz": 232},
        {"number": "G7303","type": "G", "dep": "09:30", "arr": "10:32", "dur": 62,  "2nd": 73,   "1st": 116,  "biz": 232},
        {"number": "G7309","type": "G", "dep": "14:00", "arr": "15:02", "dur": 62,  "2nd": 73,   "1st": 116,  "biz": 232},
        {"number": "G7325","type": "G", "dep": "18:30", "arr": "19:32", "dur": 62,  "2nd": 73,   "1st": 116,  "biz": 232},
    ],
    ("hangzhou", "shanghai"): [
        {"number": "G7302","type": "G", "dep": "07:30", "arr": "08:32", "dur": 62,  "2nd": 73,   "1st": 116,  "biz": 232},
        {"number": "G7304","type": "G", "dep": "10:00", "arr": "11:02", "dur": 62,  "2nd": 73,   "1st": 116,  "biz": 232},
        {"number": "G7326","type": "G", "dep": "19:00", "arr": "20:02", "dur": 62,  "2nd": 73,   "1st": 116,  "biz": 232},
    ],
    ("shanghai", "nanjing"): [
        {"number": "G103", "type": "G", "dep": "07:07", "arr": "08:20", "dur": 73,  "2nd": 160,  "1st": 256,  "biz": 512},
        {"number": "G109", "type": "G", "dep": "09:00", "arr": "10:18", "dur": 78,  "2nd": 160,  "1st": 256,  "biz": 512},
        {"number": "G7001","type": "G", "dep": "12:05", "arr": "13:18", "dur": 73,  "2nd": 160,  "1st": 256,  "biz": 512},
    ],
    ("nanjing", "shanghai"): [
        {"number": "G104", "type": "G", "dep": "07:30", "arr": "08:43", "dur": 73,  "2nd": 160,  "1st": 256,  "biz": 512},
        {"number": "G110", "type": "G", "dep": "10:00", "arr": "11:13", "dur": 73,  "2nd": 160,  "1st": 256,  "biz": 512},
    ],
    ("guangzhou", "shenzhen"): [
        {"number": "G6003","type": "G", "dep": "07:05", "arr": "07:33", "dur": 28,  "2nd": 75,   "1st": 120,  "biz": 240},
        {"number": "G6007","type": "G", "dep": "09:00", "arr": "09:28", "dur": 28,  "2nd": 75,   "1st": 120,  "biz": 240},
        {"number": "G6009","type": "G", "dep": "11:00", "arr": "11:28", "dur": 28,  "2nd": 75,   "1st": 120,  "biz": 240},
        {"number": "G6021","type": "G", "dep": "18:00", "arr": "18:28", "dur": 28,  "2nd": 75,   "1st": 120,  "biz": 240},
    ],
    ("shenzhen", "guangzhou"): [
        {"number": "G6004","type": "G", "dep": "07:30", "arr": "07:58", "dur": 28,  "2nd": 75,   "1st": 120,  "biz": 240},
        {"number": "G6010","type": "G", "dep": "10:00", "arr": "10:28", "dur": 28,  "2nd": 75,   "1st": 120,  "biz": 240},
        {"number": "G6022","type": "G", "dep": "17:00", "arr": "17:28", "dur": 28,  "2nd": 75,   "1st": 120,  "biz": 240},
    ],
    ("beijing", "tianjin"): [
        {"number": "C2001","type": "C", "dep": "07:00", "arr": "07:31", "dur": 31,  "2nd": 55,   "1st": 88,   "biz": 176},
        {"number": "C2005","type": "C", "dep": "08:30", "arr": "09:01", "dur": 31,  "2nd": 55,   "1st": 88,   "biz": 176},
        {"number": "C2009","type": "C", "dep": "12:00", "arr": "12:31", "dur": 31,  "2nd": 55,   "1st": 88,   "biz": 176},
        {"number": "C2015","type": "C", "dep": "18:30", "arr": "19:01", "dur": 31,  "2nd": 55,   "1st": 88,   "biz": 176},
    ],
    ("tianjin", "beijing"): [
        {"number": "C2002","type": "C", "dep": "07:30", "arr": "08:01", "dur": 31,  "2nd": 55,   "1st": 88,   "biz": 176},
        {"number": "C2006","type": "C", "dep": "09:00", "arr": "09:31", "dur": 31,  "2nd": 55,   "1st": 88,   "biz": 176},
        {"number": "C2016","type": "C", "dep": "19:00", "arr": "19:31", "dur": 31,  "2nd": 55,   "1st": 88,   "biz": 176},
    ],
    ("beijing", "chengdu"): [
        {"number": "G307", "type": "G", "dep": "08:00", "arr": "14:25", "dur": 385, "2nd": 669,  "1st": 1071, "biz": 2128},
        {"number": "G2003","type": "G", "dep": "10:00", "arr": "16:25", "dur": 385, "2nd": 669,  "1st": 1071, "biz": 2128},
    ],
    ("chengdu", "beijing"): [
        {"number": "G308", "type": "G", "dep": "08:00", "arr": "14:25", "dur": 385, "2nd": 669,  "1st": 1071, "biz": 2128},
        {"number": "G2004","type": "G", "dep": "12:00", "arr": "18:25", "dur": 385, "2nd": 669,  "1st": 1071, "biz": 2128},
    ],
    ("shanghai", "wuhan"): [
        {"number": "G503", "type": "G", "dep": "08:00", "arr": "11:30", "dur": 210, "2nd": 390,  "1st": 624,  "biz": 1248},
        {"number": "G505", "type": "G", "dep": "12:00", "arr": "15:30", "dur": 210, "2nd": 390,  "1st": 624,  "biz": 1248},
    ],
    ("wuhan", "shanghai"): [
        {"number": "G504", "type": "G", "dep": "08:30", "arr": "12:00", "dur": 210, "2nd": 390,  "1st": 624,  "biz": 1248},
        {"number": "G506", "type": "G", "dep": "14:00", "arr": "17:30", "dur": 210, "2nd": 390,  "1st": 624,  "biz": 1248},
    ],
    ("guangzhou", "changsha"): [
        {"number": "G1001","type": "G", "dep": "07:30", "arr": "09:36", "dur": 126, "2nd": 211,  "1st": 338,  "biz": 676},
        {"number": "G1003","type": "G", "dep": "10:00", "arr": "12:06", "dur": 126, "2nd": 211,  "1st": 338,  "biz": 676},
        {"number": "G1009","type": "G", "dep": "16:00", "arr": "18:06", "dur": 126, "2nd": 211,  "1st": 338,  "biz": 676},
    ],
    ("changsha", "guangzhou"): [
        {"number": "G1002","type": "G", "dep": "08:00", "arr": "10:06", "dur": 126, "2nd": 211,  "1st": 338,  "biz": 676},
        {"number": "G1010","type": "G", "dep": "15:00", "arr": "17:06", "dur": 126, "2nd": 211,  "1st": 338,  "biz": 676},
    ],
}


def _normalize_city(city: str) -> str:
    return city.lower().strip().replace(" ", "").replace("-", "").replace("'", "")


def _lookup_station(city: str) -> Optional[Dict]:
    key = city.lower().strip()
    if key in CHINA_STATION_MAP:
        return CHINA_STATION_MAP[key]
    # fuzzy: strip spaces/hyphens
    for k, v in CHINA_STATION_MAP.items():
        if _normalize_city(key) == _normalize_city(k):
            return v
        if _normalize_city(key) in _normalize_city(k) or _normalize_city(k) in _normalize_city(key):
            return v
    return None


def _route_key(origin: str, dest: str) -> tuple:
    return (origin.lower().strip(), dest.lower().strip())


def search_china_trains_mock(
    origin_city: str,
    destination_city: str,
    date: str,
    seat_class: Optional[str] = None,
) -> List[Dict[str, Any]]:
    orig_info = _lookup_station(origin_city)
    dest_info = _lookup_station(destination_city)

    if not orig_info or not dest_info:
        return []

    orig_key = origin_city.lower().strip()
    dest_key = destination_city.lower().strip()

    # Try direct route lookup
    route = _TRAIN_ROUTES.get((orig_key, dest_key)) or _TRAIN_ROUTES.get(
        (_normalize_city(orig_key), _normalize_city(dest_key))
    )

    # Generic fallback for unknown pairs: estimate 1 train per ~200km
    if not route:
        route = [
            {"number": "G999", "type": "G", "dep": "08:00", "arr": "12:00", "dur": 240,
             "2nd": 400, "1st": 640, "biz": 1280},
            {"number": "G1001","type": "G", "dep": "14:00", "arr": "18:00", "dur": 240,
             "2nd": 400, "1st": 640, "biz": 1280},
        ]

    # Choose price column based on seat_class
    price_key = "2nd"
    if seat_class:
        sc = seat_class.lower().replace(" ", "_").replace("class", "").strip("_")
        if "1st" in sc or sc == "first":
            price_key = "1st"
        elif "biz" in sc or "business" in sc:
            price_key = "biz"

    results = []
    for t in route:
        price_cny = t[price_key]
        price_eur = round(price_cny * CNY_TO_EUR, 0)
        dur_h = t["dur"] // 60
        dur_m = t["dur"] % 60
        dur_str = f"{dur_h}h{dur_m:02d}m"
        seat_label = {"2nd": "2nd Class", "1st": "1st Class", "biz": "Business"}[price_key]
        results.append({
            "train_id":          f"crh-{orig_key.replace(' ','')}-{dest_key.replace(' ','')}-{t['number'].lower()}",
            "train_number":      t["number"],
            "train_type":        t["type"],
            "origin_station":    orig_info["station"],
            "destination_station": dest_info["station"],
            "origin_city":       origin_city.title(),
            "destination_city":  destination_city.title(),
            "departure_time":    f"{date} {t['dep']}",
            "arrival_time":      f"{date} {t['arr']}",
            "duration":          dur_str,
            "seat_class":        seat_label,
            "price_cny":         price_cny,
            "price_eur":         price_eur,
            "booking_link":      f"https://www.trip.com/trains/{orig_info['code']}-{dest_info['code']}/{date}/",
        })

    return results
