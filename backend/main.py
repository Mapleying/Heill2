import os
import json
from dotenv import load_dotenv
load_dotenv()  # reads .env from the project root
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List
from backend.agent import ConversationalAgent

GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
AVIASALES_TOKEN    = os.getenv("AVIASALES_TOKEN")
AVIASALES_MARKER   = os.getenv("AVIASALES_MARKER")
BOOKING_AFFILIATE_ID = os.getenv("BOOKING_AFFILIATE_ID")
BOOKING_API_KEY    = os.getenv("BOOKING_API_KEY")

app = FastAPI(title="Sportcation Travel Agent API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory sessions store
agents_store: Dict[str, ConversationalAgent] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: str
    api_key: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    itinerary: Optional[Dict] = None
    suggestions: Optional[List] = None

@app.get("/api/config")
async def get_config():
    return {
        "gemini_active": bool(GEMINI_API_KEY),
        "aviasales_active": bool(AVIASALES_TOKEN),
        "booking_active": bool(BOOKING_AFFILIATE_ID and BOOKING_API_KEY),
    }

@app.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    session_id = req.session_id
    if session_id not in agents_store:
        agents_store[session_id] = ConversationalAgent(
            session_id,
            gemini_api_key=GEMINI_API_KEY,
            aviasales_token=AVIASALES_TOKEN,
            aviasales_marker=AVIASALES_MARKER,
            booking_affiliate_id=BOOKING_AFFILIATE_ID,
            booking_api_key=BOOKING_API_KEY,
        )
    agent = agents_store[session_id]

    async def generate():
        try:
            async for chunk in agent.get_response_stream(req.message, api_key=req.api_key):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            import traceback; traceback.print_exc()
            yield f"data: {json.dumps({'text': f'Error: {e}'})}\n\n"
        finally:
            yield f"data: {json.dumps({'done': True, 'itinerary': agent.state.get('itinerary'), 'suggestions': agent.state.get('_last_suggestions') or None})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    session_id = req.session_id
    print(f"[CHAT REQUEST] Session: {session_id} | Msg: {req.message} | HasKey: {bool(req.api_key)}")
    if session_id not in agents_store:
        agents_store[session_id] = ConversationalAgent(
            session_id,
            gemini_api_key=GEMINI_API_KEY,
            aviasales_token=AVIASALES_TOKEN,
            aviasales_marker=AVIASALES_MARKER,
            booking_affiliate_id=BOOKING_AFFILIATE_ID,
            booking_api_key=BOOKING_API_KEY,
        )
        
    agent = agents_store[session_id]
    
    try:
        response_text = await agent.get_response(req.message, api_key=req.api_key)
        print(f"[CHAT RESPONSE] Session: {session_id} | Resp: {response_text[:100]}...")
        return ChatResponse(
            response=response_text,
            itinerary=agent.state.get("itinerary"),
            suggestions=agent.state.get("_last_suggestions") or None,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[CHAT ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/itinerary/{session_id}")
async def get_itinerary(session_id: str):
    if session_id not in agents_store:
         return {"itinerary": None}
    return {"itinerary": agents_store[session_id].state.get("itinerary")}

@app.get("/api/export/{session_id}/{format}")
async def export_itinerary(session_id: str, format: str):
    if session_id not in agents_store or not agents_store[session_id].state.get("itinerary"):
        raise HTTPException(status_code=404, detail="Itinerary not found")
        
    itin = agents_store[session_id].state.get("itinerary")
    camp = itin["camp"]
    session = itin["session"]
    hotel = itin["hotel"]
    flight = itin["flight"]
    
    filename = f"sportcation_{session_id}.{format}"
    filepath = f"/tmp/{filename}" # local temporary file
    
    # Ensure folder exists
    os.makedirs("/tmp", exist_ok=True)
    
    if format == "ics":
        # Create a simple .ics calendar file
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Sportcation//Itinerary//EN
BEGIN:VEVENT
UID:{session_id}@sportcation.com
DTSTART:{session['start_date'].replace('-', '')}T090000Z
DTEND:{session['end_date'].replace('-', '')}T170000Z
SUMMARY:Sportcation: {camp['name']}
DESCRIPTION:Sport camp in {camp['location']['city']}. Price: €{session['price_per_person_eur']}.
LOCATION:{camp['location']['address']}
END:VEVENT
"""
        if hotel:
            ics_content += f"""BEGIN:VEVENT
UID:hotel-{session_id}@sportcation.com
DTSTART:{session['start_date'].replace('-', '')}T150000Z
DTEND:{session['end_date'].replace('-', '')}T110000Z
SUMMARY:Stay at {hotel['name']}
DESCRIPTION:Hotel stay booked via deep-link.
LOCATION:{hotel['name']}
END:VEVENT
"""
        ics_content += "END:VCALENDAR"
        
        with open(filepath, "w") as f:
            f.write(ics_content)
            
    else:
        # Create a text-based PDF/text report
        report_content = f"""SPORTCATION ITINERARY EXPORT
Session ID: {session_id}
Status: Draft Itinerary

=========================================
1. SPORT CAMP
=========================================
Camp Name: {camp['name']}
Location: {camp['location']['address']}, {camp['location']['city']}, {camp['location']['country_code']}
Dates: {session['start_date']} to {session['end_date']}
Total Price: €{session['price_per_person_eur']}

=========================================
2. HOTEL LODGING
=========================================
"""
        if hotel:
            report_content += f"""Hotel Name: {hotel['name']} ({hotel['stars']} stars)
Price/Night: €{hotel['price_per_night_eur']}
Booking Link: {hotel['booking_link']}
"""
        else:
            report_content += "No hotel selected.\n"
            
        report_content += """
=========================================
3. FLIGHT LOGISTICS
=========================================
"""
        if flight:
            report_content += f"""Airline: {flight['airline']}
Route: {flight['origin']} -> {flight['destination']}
Departure: {flight['departure_time']}
Price: €{flight['price_eur']} (Equipment fee: €{flight['equipment_fee_eur']})
Booking Link: {flight['booking_link']}
"""
        else:
            report_content += "No flights selected.\n"
            
        report_content += f"""
=========================================
TOTAL ESTIMATED COST: €{itin['total_price_eur']:.2f}
=========================================
Created via Sportcation Travel Agent.
"""
        with open(filepath, "w") as f:
            f.write(report_content)
            
    return FileResponse(
        filepath, 
        media_type="application/octet-stream" if format == "ics" else "text/plain", 
        filename=filename
    )

# Serve Frontend files
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return FileResponse("/home/tsy629/git/Heill/frontend/index.html")

@app.get("/style.css")
async def serve_css():
    return FileResponse("/home/tsy629/git/Heill/frontend/style.css")

@app.get("/app.js")
async def serve_js():
    return FileResponse("/home/tsy629/git/Heill/frontend/app.js")
