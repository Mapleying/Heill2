"""Run once to populate Supabase tables from mock data."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]
sb  = create_client(url, key)

# ── Camps ─────────────────────────────────────────────────────────────────────
camps = [
    {"camp_id":"tennis-lamanga","name":"La Manga Club Tennis Camp","sport":"tennis","camp_type":"residential","operator_name":"La Manga Tennis Ltd","operator_verified":True,"address":"La Manga Club, 30389 Carretera de Atamaría","city":"Murcia","country_code":"ES","lat":37.6047,"lng":-0.8021,"skill_level_min":"ntrp_3.0","skill_level_max":"ntrp_6.0","max_group_size":6,"solo_friendly":True,"language_of_instruction":["English","Spanish"],"amenities":["tennis_courts","gym","pool","early_breakfast","spa"],"cancellation_policy":"Moderate (14 days free cancellation)","source":"partner_api","average_review_score":4.8,"review_count":142},
    {"camp_id":"tennis-nadal","name":"Rafa Nadal Academy Elite Camp","sport":"tennis","camp_type":"residential","operator_name":"RNA Group","operator_verified":True,"address":"Ctra. Cales de Mallorca s/n, km 1.2","city":"Manacor, Mallorca","country_code":"ES","lat":39.5772,"lng":3.2208,"skill_level_min":"ntrp_3.5","skill_level_max":"ntrp_7.0","max_group_size":4,"solo_friendly":True,"language_of_instruction":["English","Spanish","French"],"amenities":["tennis_courts","gym","pool","early_breakfast","restaurant","physio"],"cancellation_policy":"Strict (No refund within 30 days)","source":"partner_api","average_review_score":4.9,"review_count":289},
    {"camp_id":"ski-chamonix","name":"Chamonix Off-Piste Freeride Camp","sport":"skiing","camp_type":"clinic","operator_name":"Chamonix Mountain Guides","operator_verified":True,"address":"190 Place de l'Eglise","city":"Chamonix-Mont-Blanc","country_code":"FR","lat":45.9227,"lng":6.8685,"skill_level_min":"ski_intermediate","skill_level_max":"ski_expert","max_group_size":5,"solo_friendly":True,"language_of_instruction":["English","French"],"amenities":["ski_storage","early_breakfast","sauna"],"cancellation_policy":"Flexible (48h free cancellation)","source":"internal","average_review_score":4.7,"review_count":94},
    {"camp_id":"ski-valthorens","name":"Val Thorens Altitude Ski Academy","sport":"skiing","camp_type":"residential","operator_name":"ESF Val Thorens","operator_verified":True,"address":"Maison de Val Thorens","city":"Val Thorens","country_code":"FR","lat":45.2982,"lng":6.5800,"skill_level_min":"ski_beginner","skill_level_max":"ski_advanced","max_group_size":8,"solo_friendly":False,"language_of_instruction":["English","French","German"],"amenities":["ski_storage","pool","early_breakfast","ski_in_ski_out"],"cancellation_policy":"Moderate (14 days free cancellation)","source":"scraped","average_review_score":4.6,"review_count":112},
    {"camp_id":"surf-ericeira","name":"Ericeira Surf Camp & Yoga Retreat","sport":"surfing","camp_type":"residential","operator_name":"Ericeira Waves Group","operator_verified":True,"address":"Rua dos Surfistas, No. 5","city":"Ericeira","country_code":"PT","lat":38.9634,"lng":-9.4124,"skill_level_min":"surf_beginner","skill_level_max":"surf_intermediate","max_group_size":6,"solo_friendly":True,"language_of_instruction":["English","Portuguese","German"],"amenities":["surf_rinse_station","yoga_deck","pool","early_breakfast","surfboard_rental"],"cancellation_policy":"Flexible (7 days free cancellation)","source":"partner_api","average_review_score":4.9,"review_count":320},
    {"camp_id":"surf-hossegor","name":"Hossegor Performance Surf Center","sport":"surfing","camp_type":"clinic","operator_name":"Landes Surf Academy","operator_verified":True,"address":"Plage des Estagnots","city":"Hossegor","country_code":"FR","lat":43.6841,"lng":-1.4325,"skill_level_min":"surf_intermediate","skill_level_max":"surf_advanced","max_group_size":4,"solo_friendly":True,"language_of_instruction":["English","French"],"amenities":["surf_rinse_station","video_analysis","gym"],"cancellation_policy":"Strict (No refund within 14 days)","source":"internal","average_review_score":4.8,"review_count":86},
]

sessions = [
    {"session_id":"session-tennis-lamanga-1","camp_id":"tennis-lamanga","start_date":"2026-07-05","end_date":"2026-07-11","capacity":12,"spots_remaining":4,"price_per_person_eur":1200.0},
    {"session_id":"session-tennis-lamanga-2","camp_id":"tennis-lamanga","start_date":"2026-07-19","end_date":"2026-07-25","capacity":12,"spots_remaining":6,"price_per_person_eur":1250.0},
    {"session_id":"session-tennis-lamanga-3","camp_id":"tennis-lamanga","start_date":"2026-08-02","end_date":"2026-08-08","capacity":12,"spots_remaining":0,"price_per_person_eur":1300.0},
    {"session_id":"session-tennis-nadal-1","camp_id":"tennis-nadal","start_date":"2026-07-12","end_date":"2026-07-18","capacity":20,"spots_remaining":2,"price_per_person_eur":2100.0},
    {"session_id":"session-tennis-nadal-2","camp_id":"tennis-nadal","start_date":"2026-08-09","end_date":"2026-08-15","capacity":20,"spots_remaining":8,"price_per_person_eur":2200.0},
    {"session_id":"session-ski-chamonix-1","camp_id":"ski-chamonix","start_date":"2027-01-10","end_date":"2027-01-16","capacity":10,"spots_remaining":3,"price_per_person_eur":950.0},
    {"session_id":"session-ski-chamonix-2","camp_id":"ski-chamonix","start_date":"2027-02-07","end_date":"2027-02-13","capacity":10,"spots_remaining":5,"price_per_person_eur":1100.0},
    {"session_id":"session-ski-valthorens-1","camp_id":"ski-valthorens","start_date":"2027-01-17","end_date":"2027-01-23","capacity":16,"spots_remaining":7,"price_per_person_eur":850.0},
    {"session_id":"session-ski-valthorens-2","camp_id":"ski-valthorens","start_date":"2027-02-14","end_date":"2027-02-20","capacity":16,"spots_remaining":12,"price_per_person_eur":900.0},
    {"session_id":"session-surf-ericeira-1","camp_id":"surf-ericeira","start_date":"2026-07-12","end_date":"2026-07-18","capacity":15,"spots_remaining":5,"price_per_person_eur":750.0},
    {"session_id":"session-surf-ericeira-2","camp_id":"surf-ericeira","start_date":"2026-08-02","end_date":"2026-08-08","capacity":15,"spots_remaining":2,"price_per_person_eur":800.0},
    {"session_id":"session-surf-ericeira-3","camp_id":"surf-ericeira","start_date":"2026-09-13","end_date":"2026-09-19","capacity":15,"spots_remaining":9,"price_per_person_eur":700.0},
    {"session_id":"session-surf-hossegor-1","camp_id":"surf-hossegor","start_date":"2026-07-19","end_date":"2026-07-25","capacity":8,"spots_remaining":3,"price_per_person_eur":990.0},
    {"session_id":"session-surf-hossegor-2","camp_id":"surf-hossegor","start_date":"2026-08-23","end_date":"2026-08-29","capacity":8,"spots_remaining":4,"price_per_person_eur":1050.0},
]

hotels = [
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

airports = [
    {"city":"Murcia","iata":"RMU","name":"Murcia International Airport","transfer_time_mins":30},
    {"city":"Murcia","iata":"ALC","name":"Alicante-Elche Airport","transfer_time_mins":75},
    {"city":"Manacor, Mallorca","iata":"PMI","name":"Palma de Mallorca Airport","transfer_time_mins":45},
    {"city":"Chamonix-Mont-Blanc","iata":"GVA","name":"Geneva Airport","transfer_time_mins":75},
    {"city":"Chamonix-Mont-Blanc","iata":"LYS","name":"Lyon-Saint Exupéry Airport","transfer_time_mins":140},
    {"city":"Val Thorens","iata":"GVA","name":"Geneva Airport","transfer_time_mins":150},
    {"city":"Val Thorens","iata":"LYS","name":"Lyon-Saint Exupéry Airport","transfer_time_mins":150},
    {"city":"Val Thorens","iata":"CMF","name":"Chambéry-Savoie Airport","transfer_time_mins":90},
    {"city":"Ericeira","iata":"LIS","name":"Humberto Delgado Airport (Lisbon)","transfer_time_mins":40},
    {"city":"Hossegor","iata":"BIQ","name":"Biarritz Pays Basque Airport","transfer_time_mins":35},
    {"city":"Hossegor","iata":"BOD","name":"Bordeaux-Mérignac Airport","transfer_time_mins":110},
]

def upsert(table, rows):
    res = sb.table(table).upsert(rows).execute()
    print(f"  {table}: {len(res.data)} rows upserted")

print("Seeding Supabase...")
upsert("camps", camps)
upsert("camp_sessions", sessions)
upsert("hotels", hotels)
upsert("airport_mapping", airports)
print("Done.")
