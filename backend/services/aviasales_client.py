import httpx
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

TRAVELPAYOUTS_BASE = "https://api.travelpayouts.com"

AIRLINE_NAMES: Dict[str, str] = {
    "IB": "Iberia", "AF": "Air France", "TP": "TAP Portugal",
    "LH": "Lufthansa", "U2": "easyJet", "FR": "Ryanair",
    "VY": "Vueling", "BA": "British Airways", "EI": "Aer Lingus",
    "KL": "KLM", "SN": "Brussels Airlines", "AZ": "ITA Airways",
    "BT": "airBaltic", "W6": "Wizz Air", "PC": "Pegasus",
    "HV": "Transavia", "TO": "Transavia France",
}

EQUIPMENT_FEES: Dict[str, float] = {
    "skis": 50.0, "snowboard": 50.0, "surfboard": 70.0,
}


class AviasalesClient:
    def __init__(self, token: str, marker: Optional[str] = None):
        self.token = token
        self.marker = marker

    async def search_flights(
        self,
        origin_iata: str,
        destination_iata_list: List[str],
        date: str,
        equipment_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        equip_fee = EQUIPMENT_FEES.get((equipment_type or "").lower(), 0.0)
        all_offers: List[Dict[str, Any]] = []

        for dest_iata in destination_iata_list[:3]:
            offers = await self._prices_for_dates(origin_iata, dest_iata, date, equip_fee)
            if not offers:
                offers = await self._month_matrix(origin_iata, dest_iata, date, equip_fee)
            all_offers.extend(offers)

        return all_offers

    async def _prices_for_dates(
        self, origin: str, dest: str, date: str, equip_fee: float
    ) -> List[Dict[str, Any]]:
        """Exact-date cache lookup. Best when the route has recent search traffic."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{TRAVELPAYOUTS_BASE}/aviasales/v3/prices_for_dates",
                    params={
                        "origin": origin.upper(),
                        "destination": dest.upper(),
                        "departure_at": date,
                        "currency": "eur",
                        "sorting": "price",
                        "limit": 3,
                        "token": self.token,
                    },
                )
                if resp.status_code != 200:
                    return []
                items = resp.json().get("data", [])
            return [self._normalize_v3(item, equip_fee) for item in items]
        except Exception:
            return []

    async def _month_matrix(
        self, origin: str, dest: str, date: str, equip_fee: float
    ) -> List[Dict[str, Any]]:
        """
        Monthly cheapest-price matrix. Better coverage than prices_for_dates.
        Filters to results within ±3 days of the requested date.
        """
        try:
            month = date[:7]  # YYYY-MM
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{TRAVELPAYOUTS_BASE}/v2/prices/month-matrix",
                    params={
                        "origin": origin.upper(),
                        "destination": dest.upper(),
                        "currency": "eur",
                        "token": self.token,
                        "month": month,
                        "show_to_affiliates": "true",
                    },
                )
                if resp.status_code != 200:
                    return []
                items = resp.json().get("data", [])

            target = datetime.strptime(date, "%Y-%m-%d")
            nearby = [
                item for item in items
                if abs((datetime.strptime(item["depart_date"], "%Y-%m-%d") - target).days) <= 3
            ]
            # If nothing close, take cheapest 3 in the month
            if not nearby:
                nearby = sorted(items, key=lambda x: x.get("value", 9999))[:3]

            return [self._normalize_matrix(item, origin, dest, equip_fee) for item in nearby[:3]]
        except Exception:
            return []

    def _normalize_v3(self, item: Dict, equip_fee: float) -> Dict[str, Any]:
        airline_code = item.get("airline", "??")
        airline_name = AIRLINE_NAMES.get(airline_code, airline_code)
        raw_link = item.get("link", "")
        booking_link = self._make_link(raw_link, item.get("origin", ""), item.get("destination", ""), item.get("departure_at", "")[:10])
        return {
            "flight_id": f"aviasales-{item.get('origin','')}-{item.get('destination','')}-{item.get('departure_at','')[:10]}-{airline_code}",
            "airline": airline_name,
            "origin": item.get("origin_airport") or item.get("origin", ""),
            "destination": item.get("destination_airport") or item.get("destination", ""),
            "departure_time": item.get("departure_at", ""),
            "arrival_time": "",
            "stops": item.get("transfers", 0),
            "price_eur": float(item.get("price", 0)),
            "baggage_allowance": "Check airline website",
            "equipment_fee_eur": equip_fee,
            "booking_link": booking_link,
        }

    def _normalize_matrix(self, item: Dict, origin: str, dest: str, equip_fee: float) -> Dict[str, Any]:
        depart_date = item.get("depart_date", "")
        gate = item.get("gate", "")  # booking platform, e.g. "Kiwi.com"
        booking_link = self._make_link("", origin, dest, depart_date)
        return {
            "flight_id": f"aviasales-{origin}-{dest}-{depart_date}-matrix",
            "airline": gate or "See booking link",
            "origin": origin.upper(),
            "destination": dest.upper(),
            "departure_time": depart_date,
            "arrival_time": "",
            "stops": item.get("number_of_changes", 0),
            "price_eur": float(item.get("value", 0)),
            "baggage_allowance": "Check airline website",
            "equipment_fee_eur": equip_fee,
            "booking_link": booking_link,
        }

    def _make_link(self, raw_link: str, origin: str, dest: str, date_str: str) -> str:
        marker_suffix = f"?marker={self.marker}" if self.marker else ""
        if raw_link:
            return f"https://www.aviasales.com{raw_link}{marker_suffix}"
        # Construct search link: /search/LHR0507RMU1
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            date_part = d.strftime("%d%m")
        except Exception:
            date_part = "0101"
        return f"https://www.aviasales.com/search/{origin.upper()}{date_part}{dest.upper()}1{marker_suffix}"
