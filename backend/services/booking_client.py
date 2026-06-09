import base64
import httpx
from typing import Optional, List, Dict, Any

BOOKING_BASE = "https://distribution-xml.booking.com/2.9/json"

# Booking.com facility IDs → our amenity strings
FACILITY_MAP: Dict[int, str] = {
    11: "pool",        # Swimming pool (outdoor)
    109: "pool",       # Swimming pool (indoor)
    28: "gym",
    433: "tennis_courts",
    430: "ski_in_ski_out",
    456: "ski_storage",
    16: "restaurant",
    45: "early_breakfast",
    "surf": "surf_rinse_station",  # not a standard facility; added via name heuristic
}


class BookingClient:
    def __init__(self, affiliate_id: str, api_key: str):
        creds = f"{affiliate_id}:{api_key}"
        self._auth_header = "Basic " + base64.b64encode(creds.encode()).decode()

    async def search_hotels(
        self,
        lat: float,
        lng: float,
        check_in: str,
        check_out: str,
        amenities: Optional[List[str]] = None,
        radius_km: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Searches Booking.com Affiliate Demand API by coordinates.
        Returns normalised hotel list.
        """
        params: Dict[str, Any] = {
            "latitude": round(lat, 4),
            "longitude": round(lng, 4),
            "radius": radius_km,
            "checkin": check_in,
            "checkout": check_out,
            "room1": "A",
            "currency": "EUR",
            "languagecode": "en",
            "rows": 10,
            "min_review_score": 7.0,
            "order_by": "popularity",
            "extras": "hotel_facilities",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{BOOKING_BASE}/hotels",
                params=params,
                headers={"Authorization": self._auth_header},
            )
            resp.raise_for_status()
            hotels = resp.json().get("result", [])

        results = [self._normalize(h, check_in, check_out) for h in hotels]

        # Post-filter by requested amenities (at least one match)
        if amenities:
            results = [
                h for h in results
                if any(a in h["amenities"] for a in amenities)
            ] or results  # fall back to all if no matches

        return results

    def _normalize(self, h: Dict, check_in: str, check_out: str) -> Dict[str, Any]:
        facility_ids: List[int] = [
            f.get("facility_id", 0)
            for f in h.get("hotel_facilities", [])
            if isinstance(f, dict)
        ]
        amenities = list({
            FACILITY_MAP[fid]
            for fid in facility_ids
            if fid in FACILITY_MAP
        })
        # Heuristic: add surf amenity if hotel name/desc mentions it
        name = h.get("hotel_name", "")
        if "surf" in name.lower():
            amenities.append("surf_rinse_station")

        nights = 1
        try:
            from datetime import date as dt
            d1 = dt.fromisoformat(check_in)
            d2 = dt.fromisoformat(check_out)
            nights = max((d2 - d1).days, 1)
        except Exception:
            pass

        total_price = float(h.get("min_total_price") or 0.0)
        price_per_night = round(total_price / nights, 2) if total_price else 0.0

        stars_raw = h.get("hotel_rating") or h.get("class") or 3
        try:
            stars = int(float(str(stars_raw)))
        except Exception:
            stars = 3

        hotel_id = str(h.get("hotel_id", "unknown"))
        return {
            "hotel_id": f"booking-{hotel_id}",
            "name": name,
            "lat": float(h.get("latitude", 0)),
            "lng": float(h.get("longitude", 0)),
            "stars": stars,
            "amenities": amenities,
            "price_per_night_eur": price_per_night,
            "booking_link": h.get("url", f"https://www.booking.com/hotel/id/{hotel_id}.html"),
            "sport_partner": False,
            "review_score": float(h.get("review_score") or 0),
        }
