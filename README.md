# Heill — Sportcation AI Travel Agent

An AI-powered travel agent that plans sport-focused vacations. The sport camp is the fixed anchor event; flights and hotels are automatically searched around it.

Supported sports: **Tennis · Skiing / Snowboarding · Surfing**

---

## What it does

1. **Finds camps** matching your sport, skill level, and region
2. **Asks travel questions** — departure city, party size, preferred dates
3. **Searches real flights** (Aviasales / Travelpayouts) from your origin
4. **Searches hotels** nearby the camp venue (Booking.com Affiliate API)
5. **Builds an itinerary** with conflict detection and booking deep-links
6. **Exports** as PDF summary or `.ics` calendar

The agent is powered by **Google Gemini 2.5 Flash** with native function-calling. When Gemini is not configured, a keyword-driven simulation mode handles the full flow.

---

## Architecture

```
Browser (Vanilla JS + CSS)
        │  REST (JSON)
        ▼
FastAPI server  ──────────────────────────────────────────┐
  /api/chat          ConversationalAgent                  │
  /api/config        │                                    │
  /api/itinerary     ├─ _run_gemini_agent()  ◄── Gemini 2.5 Flash
  /api/export        │     └─ execute_tool() ─────────────┤
                     │           ├─ search_sport_camps    │ Camp DB
                     │           ├─ get_sport_camp_details│ (in-memory)
                     │           ├─ search_flights ───────┼── Aviasales API
                     │           ├─ search_hotels ────────┼── Booking.com API
                     │           └─ create_itinerary_draft│
                     │                                    │
                     └─ _run_mock_agent()   (fallback)    │
                           keyword-NLU, same tools ───────┘
```

### Key files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app, endpoints, env-var loading |
| `backend/agent.py` | Gemini agentic loop, mock agent, NLU helpers, tool dispatcher |
| `backend/database.py` | In-memory camp catalog, airport mapping, mock search fallbacks |
| `backend/services/aviasales_client.py` | Travelpayouts flight search (real prices) |
| `backend/services/booking_client.py` | Booking.com Affiliate hotel search |
| `frontend/index.html` | Single-page chat UI with live itinerary sidebar |
| `frontend/app.js` | Chat logic, suggestion card rendering, itinerary panel updates |
| `frontend/style.css` | Dark/light theme, CSS Grid layout, card components |

---

## Prerequisites

- Python 3.11+
- A virtual environment (`venv/`)

---

## Setup

### 1. Clone and create the virtual environment

```bash
git clone <repo-url>
cd Heill
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
# Required for natural language understanding
GEMINI_API_KEY=AIzaSy...          # https://aistudio.google.com/app/apikey

# Required for real flight prices
AVIASALES_TOKEN=...               # https://travelpayouts.com → Account → API Tokens
AVIASALES_MARKER=...              # Affiliate marker (optional, embeds in booking links)

# Optional — hotel search via Booking.com Affiliate API (requires partner approval)
BOOKING_AFFILIATE_ID=...          # https://www.booking.com/affiliate-program
BOOKING_API_KEY=...
```

### 3. Start the server

```bash
set -a && source .env && set +a
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open the app

- **Local machine:** http://localhost:8000
- **WSL2 / remote:** http://`hostname -I | awk '{print $1}'`:8000

---

## API Keys

| Service | Free tier | Purpose |
|---|---|---|
| [Google AI Studio](https://aistudio.google.com/app/apikey) | Yes — generous daily quota | Powers the Gemini LLM |
| [Travelpayouts](https://travelpayouts.com) | Yes — free with attribution | Real flight prices |
| [Booking.com Affiliate](https://www.booking.com/affiliate-program/partner/signup) | Yes — requires partner approval (~days) | Real hotel search |

Without any keys the app runs in simulation mode using mock flight and hotel data.

---

## Conversation flow

```
User: "I want to plan a tennis camp in Spain"
  → Agent searches camps, shows clickable camp cards

User: clicks a camp card
  → Agent asks:
      1. Where are you flying from?
      2. Solo or with others?
      3. When do you want to depart?

User: "Flying from Hong Kong, solo, day before the camp"
  → Agent parses HKG / 1 traveler / camp start − 1 day
  → Searches real flights from HKG + hotels near camp
  → Shows clickable flight and hotel cards

User: clicks flight card + hotel card
  → Itinerary panel updates in real time

User: "checkout"
  → Full itinerary summary with booking deep-links
  → Export as PDF or .ics
```

The agent understands natural changes mid-conversation:
- "Actually, fly from London instead" → re-searches flights from LHR
- "We're a family of four" → updates traveler count
- "What about the Rafa Nadal Academy instead?" → switches camp, clears prior results

---

## Camp catalog (MVP)

| Camp | Sport | Location | Skill range |
|---|---|---|---|
| La Manga Club Tennis Camp | Tennis | Murcia, Spain | NTRP 3.0 – 6.0 |
| Rafa Nadal Academy Elite Camp | Tennis | Mallorca, Spain | NTRP 3.5 – 7.0 |
| Chamonix Off-Piste Freeride Camp | Skiing | Chamonix, France | Intermediate – Expert |
| Val Thorens Altitude Ski Academy | Skiing | Val Thorens, France | Beginner – Advanced |
| Ericeira Surf Camp & Yoga Retreat | Surfing | Ericeira, Portugal | Beginner – Intermediate |
| Hossegor Performance Surf Center | Surfing | Hossegor, France | Intermediate – Advanced |

---

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/config` | Returns `{gemini_active, aviasales_active, booking_active}` |
| `POST` | `/api/chat` | Send a message; returns `{response, itinerary, suggestions}` |
| `GET` | `/api/itinerary/{session_id}` | Fetch current itinerary state |
| `GET` | `/api/export/{session_id}/pdf` | Download text itinerary summary |
| `GET` | `/api/export/{session_id}/ics` | Download `.ics` calendar file |

**Chat request body:**
```json
{
  "message": "I want a tennis camp in Spain",
  "session_id": "sess_abc123",
  "api_key": null
}
```

`api_key` is optional — if omitted the server uses its configured `GEMINI_API_KEY`.

---

## Graceful degradation

| Scenario | Behaviour |
|---|---|
| `GEMINI_API_KEY` missing | Falls back to keyword-based mock agent |
| Aviasales returns no results | Falls back to mock flight data |
| Booking.com not configured | Falls back to mock hotel data |
| Any external API error | Catches exception, uses mock data, never crashes |

---

## Itinerary export

### PDF (text)
Download via the **Export PDF Summary** button in the sidebar or `GET /api/export/{session_id}/pdf`.

### Calendar (.ics)
Download via **Export Calendar (.ics)** or `GET /api/export/{session_id}/ics`. Creates calendar events for the camp session and hotel check-in.

---

## Project structure

```
Heill/
├── .env.example                 # Environment variable template
├── requirements.txt             # Python dependencies
├── backend/
│   ├── main.py                  # FastAPI server
│   ├── agent.py                 # Agent logic (Gemini + mock)
│   ├── database.py              # Camp catalog, airport mapping
│   └── services/
│       ├── aviasales_client.py  # Travelpayouts flight API
│       └── booking_client.py    # Booking.com hotel API
└── frontend/
    ├── index.html               # App shell
    ├── style.css                # Dark/light theme
    └── app.js                   # Chat UI, suggestion cards, itinerary panel
```

---

## Known limitations (MVP)

- Camp catalog is curated and static (6 camps across Europe)
- No user accounts or persistent itinerary storage — session state is in-memory and lost on server restart
- Bookings are via external deep-links only — no in-app payment processing
- Hotel search requires Booking.com partner approval (free but takes a few days)
- Golf, padel, cycling, and other sports are not yet supported
