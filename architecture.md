# Sportcation Travel Agent — System Specification & Architecture (MVP)

An AI-powered travel agent that helps customers plan sport-focused vacations ("sportcations") — tennis camps, ski trips, surf schools, and similar. The sport activity is the fixed anchor event; all logistics (flights, hotels) are planned around it.

---

## 1. System Overview

**Problem:** Planning a sportcation requires simultaneous coordination of a sport camp (right skill level, right dates), flights (arriving before camp starts, nearby airport), and a hotel (close to venue, sport-friendly amenities). No unified tool does this today — customers juggle 4-6 separate tools and manually cross-reference everything.

**Target Users:**
- Primary: Active adults (25-55) traveling to participate in sport
- Secondary: Corporate HR booking team sport retreats
- Tertiary: Parents booking youth sport academies

**Value Proposition:** One conversation that finds a camp matching the user's sport and skill level, then plans flights and hotels around it — producing a coherent, exportable itinerary.

**MVP Scope:** Sports supported are tennis, skiing/snowboarding, and surfing. All bookings are via deep-links to external providers (no payment processing through Sportcation in MVP).

---

## 2. Functional Requirements

### 2.1 Sport Activity Discovery

Supported sports (MVP): tennis, skiing/snowboarding, surfing.

- Search by: sport, date range, duration, skill level, geography (country/region), camp type (residential/day/clinic)
- Skill levels are sport-specific:
  - Tennis: NTRP scale (1.0–7.0)
  - Skiing/Snowboarding: Beginner / Intermediate / Advanced / Expert
  - Surfing: Beginner (standing up) / Intermediate (green waves) / Advanced (overhead surf)
- Availability tracking: spots remaining, waitlist status, data freshness timestamp ("last checked X hours ago")
- Filters: solo-friendly, adult-only vs. family-friendly, language of instruction, max group size

### 2.2 Flight Search

- Search by origin airport, destination (auto-inferred from camp coordinates), date range, cabin class, passengers
- Auto-rank nearby airports by transfer time to camp venue (e.g., Val Thorens → Lyon, Geneva, Chambéry)
- Surface sport equipment surcharges (ski bags, surfboards) in price comparison
- Present results with price, duration, stops, airline, baggage allowance, equipment fee estimate
- Booking: deep-link to airline or OTA (no direct booking in MVP)

### 2.3 Hotel Search

- Search anchored on camp venue coordinates (default 5km radius, adjustable)
- Sport-friendly amenity filters: tennis courts, ski storage, surf rinse station, gym, pool, early breakfast
- Flag "sport partner hotels" with formal arrangements with nearby camps (shuttle service, equipment discounts)
- Booking: deep-link to Booking.com or Expedia (no direct booking in MVP)

### 2.4 User Profile & Preferences

- Stored per user: sport profiles with skill levels, travel preferences (cabin class, hotel star minimum, budget), owned equipment, dietary requirements
- Pre-loaded into each conversation so the agent never re-asks stored preferences
- Updated automatically when new preferences are expressed during conversation

### 2.5 Itinerary Management

- Assembles confirmed camp + flight + hotel into a day-by-day timeline
- Conflict detection: flags if outbound flight lands after camp check-in deadline, or return flight departs before last camp session ends
- Export: PDF and .ics calendar formats
- No in-app booking tracking in MVP (bookings completed externally via deep-links)

---

## 3. Non-Functional Requirements

| Concern | Target |
|---|---|
| Agent response (no external API calls) | < 3 seconds |
| Combined search results (flights + hotels) | < 8 seconds (parallel execution) |
| Agent uptime | 99.9% |
| Concurrent sessions | 500 |
| Camp availability refresh | Every 6 hours |
| Conversation context | 40+ turns without loss |

All external API calls require circuit breakers with graceful fallback messages ("Flight search is temporarily unavailable — I can hold your camp selection while you check flights separately"). A single API failure must not crash the agent.

---

## 4. System Architecture

### Component Layers

```
┌─────────────────────────────────────────┐
│  Layer 1 — Frontend                     │
│  React 18 + TypeScript                  │
│  Streaming chat UI, itinerary panel     │
│  WebSocket (chat) + REST (itineraries)  │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│  Layer 2 — API Gateway & Auth           │
│  AWS API Gateway / Kong                 │
│  Auth0 JWT, rate limiting               │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│  Layer 3 — Conversational Agent Service │
│  Python FastAPI                         │
│  Antigravity / Gemini API orchestration │
│  Parallel tool dispatch (asyncio)       │
│  Redis-backed conversation state        │
└──────┬───────┬───────────┬──────────────┘
       │       │           │
┌──────▼──┐ ┌──▼──────┐ ┌──▼───────────┐
│  Sport  │ │ Flight  │ │    Hotel     │
│  Camp   │ │ Service │ │   Service    │
│ Service │ │(Amadeus)│ │(Booking.com) │
└──────┬──┘ └─────────┘ └──────────────┘
       │
┌──────▼──────────────────────────────────┐
│  Layer 5 — Data Stores                  │
│  PostgreSQL + PostGIS (camps, users,    │
│  itineraries) · Redis (sessions)        │
│  S3 (PDF exports, camp images)          │
└─────────────────────────────────────────┘
```

### Agent Loop

```
Turn Start
  → Load conversation state from Redis
  → Fetch user profile
  → Build messages: [system_prompt, ...history, user_message]
  → Call Gemini API (with function calling)

  Loop:
    if response contains function_calls:
      → asyncio.gather(*[dispatch_tool(call) for call in function_calls])
      → Append function results to messages
      → Call Gemini API again

    if response contains text:
      → Stream text response to frontend
      → Write updated state to Redis
      → Return
```

Parallel tool execution is required — when the user soft-confirms a camp, flight and hotel searches must run concurrently, not sequentially.

---

## 5. Agent Design

### Conversational Planning Flow

1. **Sport Anchoring** — establish sport type, skill level, preferred dates, region, number of travelers
2. **Camp Selection** — present 3-5 ranked results; allow drill-down on instructor details, daily schedule, availability
3. **Logistics Planning** — on camp soft-confirm, trigger parallel flight + hotel searches automatically
4. **Itinerary Assembly** — assemble components, run conflict checks, present for user review
5. **Booking** — provide deep-links in order: camp first, then hotel, then flights

**Backtrack handling:** If the user changes the camp after flights have been searched, the agent invalidates prior flight/hotel results and re-triggers searches for the new camp location without re-asking travel preferences.

**Minimum viable clarification:** Only ask for information that cannot be inferred and is required to proceed. Batch co-required questions into a single turn (e.g., "To find the best padel camps, could you tell me: roughly which dates in October, and are you traveling solo or with others?"). Never ask hotel star rating before a camp is selected.

### Tool Definitions

| Tool | Purpose | Key Parameters |
|---|---|---|
| `search_sport_camps` | Search camp catalog | sport, location, date_range, skill_level, camp_type, solo_friendly |
| `get_sport_camp_details` | Full camp detail including schedule and reviews | camp_id |
| `get_airport_options` | Nearest airports to camp, ranked by transfer time | camp_location_coordinates, max_transfer_minutes |
| `search_flights` | Flight options with equipment fee estimates | origin_iata, destination_iata_options[], outbound_date, return_date, passengers, sport_equipment_type |
| `search_hotels` | Hotels near camp venue with sport amenity filters | venue_coordinates, check_in_date, check_out_date, guests, sport_amenities[], max_distance_km |
| `create_itinerary_draft` | Assemble components + run conflict detection | camp_id, outbound_flight_id, return_flight_id, hotel_id, user_id |
| `get_user_profile` | Load stored user preferences | user_id |
| `update_user_profile` | Persist preferences expressed during conversation | user_id, updates |

### Hallucination Prevention

- System prompt must explicitly state: "Never assert camp details (prices, dates, instructor names, availability) from memory. All such information must originate from tool results."
- Skill level taxonomy for all three sports is embedded as a structured reference in the system prompt.
- Camp data displayed in the UI is always labeled "sourced from Sportcation database."

---

## 6. Data Model

### Entities

**User**
- `user_id` (UUID), `email`, `name`, `nationality_code` (ISO 3166-1)
- `sport_profiles` (JSON array of SportProfile)
- `travel_preferences` (JSON: preferred cabin class, min hotel stars, budget per component)
- `equipment_owned` (string array: e.g., `["skis", "ski_boots"]`)
- `dietary_requirements` (string array)

**SportProfile** (embedded in User)
- `sport` (enum: tennis | skiing | snowboarding | surfing)
- `skill_level` (canonical string: e.g., `"ntrp_3.5"`, `"ski_intermediate"`, `"surf_beginner"`)
- `years_experience` (integer)
- `coaching_interest` (boolean)

**SportCamp**
- `camp_id` (UUID), `name`, `sport` (enum), `camp_type` (enum: residential | day | clinic)
- `operator_name`, `operator_verified` (boolean)
- `location` (address + city + country_code + lat/lng)
- `skill_level_min`, `skill_level_max` (canonical skill strings)
- `max_group_size` (integer), `solo_friendly` (boolean)
- `language_of_instruction` (string array)
- `amenities` (string array)
- `cancellation_policy` (string)
- `source` (enum: internal | partner_api | scraped)
- `data_refreshed_at` (timestamp)
- `average_review_score` (float), `review_count` (integer)

**CampSession** (a specific date-instance of a camp)
- `session_id` (UUID), `camp_id` (FK)
- `start_date`, `end_date`
- `capacity` (integer), `spots_remaining` (integer)
- `price_per_person_eur` (float)

**Itinerary**
- `itinerary_id` (UUID), `user_id` (FK)
- `status` (enum: draft | confirmed | completed | cancelled)
- `camp_session_id` (FK to CampSession)
- `outbound_flight` (JSON snapshot), `return_flight` (JSON snapshot)
- `hotel` (JSON snapshot)
- `timeline` (JSON array of day-by-day events)
- `conflict_warnings` (string array)
- `total_price_eur` (float)

### Relationships

- User → many Itineraries
- SportCamp → many CampSessions (CampSession is what gets booked — SportCamp is the template)
- Itinerary → one CampSession, 0–2 flight snapshots, one hotel snapshot

---

## 7. External API Integrations (MVP)

| API | Purpose | Notes |
|---|---|---|
| **Amadeus Flight Offers Search** | Flight search | Primary; supports explicit baggage/equipment fee data via `additionalInformation.equipmentBaggage` |
| **Booking.com Affiliate API (Demand API 2.0)** | Hotel search | Primary; 28M+ listings, strong `facility_ids` amenity filters. Requires Affiliate Partner enrollment. |
| **Expedia Rapid API** | Hotel search fallback | Secondary; covers geographic gaps in Americas |
| **Google Maps Distance Matrix** | Airport → camp transfer times | Used to rank nearby airports; ~$5/1,000 elements |
| **Auth0** | Authentication | JWT issuance, social login (Google/Apple), RBAC |

APIs deferred to post-MVP: Duffel (direct flight booking), Sherpa (visa advisory), Stripe (payment processing).

---

## 8. Tech Stack

| Layer | Choice | Justification |
|---|---|---|
| Backend | Python 3.12 + FastAPI | Native async for parallel tool dispatch; best Google GenAI SDK support |
| AI — agent | `gemini-2.5-pro` (via Google GenAI) | Sufficient reasoning for multi-step travel planning, long context, and native tool-calling |
| AI — preprocessing | `gemini-2.5-flash` | Intent classification, camp description summarization |
| Context caching | Gemini Context Caching | Cache system prompts and tool definitions; ~60-70% token cost reduction per turn |
| Primary DB | PostgreSQL 16 + PostGIS (via Supabase) | Geo queries for camp/hotel proximity; relational integrity for itineraries |
| Session cache | Redis 7 (Upstash) | Conversation state (2h TTL); search result cache (30m TTL) |
| Object store | AWS S3 or Cloudflare R2 | PDF itinerary exports, camp images |
| Frontend | React 18 + TypeScript + shadcn/ui | Streaming chat via Vercel AI SDK or direct SSE; Mapbox GL/Leaflet for maps |
| Deployment | Railway or Render | Simple container hosting sufficient for MVP scale (500 concurrent sessions) |
| CI/CD | GitHub Actions | Build, test, deploy pipeline |
| LLM observability | Langfuse | Per-turn cost, tool call frequency, prompt debugging |
| App observability | OpenTelemetry → Honeycomb | End-to-end trace per conversation turn |

---

## 9. MVP Scope & Success Criteria

**In scope:**
- Sports: tennis, skiing/snowboarding, surfing
- 500+ manually curated camps in Europe and key global destinations (mocked/seeded for the local MVP)
- Flight search (Amadeus) + hotel search (Booking.com) with deep-link booking only (mocked/mockable clients for MVP)
- Full 5-stage conversational agent (sport, camp, flights, hotel, itinerary)
- Web frontend (no mobile)
- PDF and .ics itinerary export
- Basic user profile persistence

**Out of scope for MVP:**
- Direct booking or payment processing through Sportcation
- Visa advisory
- Golf, padel, cycling, and other sports
- Mobile app
- Real-time camp availability webhooks
- Corporate/group accounts

**Gate metrics:** 1,000 active users by month 4; >40% of conversations reach itinerary assembly stage.

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Camp availability staleness | Display "last checked X hours ago"; refresh every 6 hours; note availability is not guaranteed until booked directly with operator |
| API cost compounding (multiple flight/hotel searches per session) | Cache search results in Redis for session duration; Gemini Context Caching reduces per-turn token cost 60-70% |
| Gemini hallucinating camp details | System prompt explicitly forbids asserting camp specifics from parametric memory; all details must originate from tool results |
| Amadeus API single-point failure | Circuit breaker with graceful fallback message; agent can continue camp/hotel planning while flights are unavailable |
| EU Package Travel Directive | MVP is referral-only (deep-links); Sportcation is not the booking agent, sidestepping most regulatory obligations |

---

## 11. Verification Plan

1. **Agent loop correctness:** Send a multi-turn conversation for a tennis camp. Verify tool calls are made in the right order, flight + hotel searches run in parallel (check traces/logs for concurrent tool calls), and changing the camp mid-conversation invalidates prior results and re-triggers searches.
2. **Tool dispatch:** Unit test each tool with mocked external APIs. Integration test against Amadeus sandbox and Booking.com test environment.
3. **Conflict detection:** Construct an itinerary where the return flight departs during the last camp session. Verify `conflict_warnings` is non-empty.
4. **Context caching:** Check Gemini traces to confirm caching is active after the first turn in any conversation.
5. **Cost target:** Run 100 simulated full planning conversations and verify average cost-per-conversation is under $0.15.

---

## 12. Implementation Order

Start with these files — each one unblocks the next:

1. `/backend/agent/agent_service.py` — core agentic loop (Gemini API calls, parallel tool dispatch, streaming)
2. `/backend/agent/tools/tool_registry.py` — all tool schemas in Gemini's function calling format + dispatch routing map
3. `/backend/services/sport_camp/search.py` — PostGIS geo+filter query builder with skill level normalization
4. `/backend/services/flight/amadeus_client.py` — Amadeus API wrapper with equipment fee handling
5. `/backend/models/itinerary.py` — SQLAlchemy models: User, SportCamp, CampSession, Itinerary (foundational to all data flows)
