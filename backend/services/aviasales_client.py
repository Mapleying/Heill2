import httpx
from datetime import datetime
from typing import Optional, List, Dict, Any

TRAVELPAYOUTS_BASE = "https://api.travelpayouts.com"

# Airport → city code (Travelpayouts uses city codes for best coverage)
AIRPORT_TO_CITY: Dict[str, str] = {
    # UK
    "LHR": "LON", "LGW": "LON", "STN": "LON", "LTN": "LON", "LCY": "LON",
    "MAN": "MAN", "BHX": "BHX", "EDI": "EDI", "GLA": "GLA", "BRS": "BRS",
    # Ireland
    "DUB": "DUB",
    # France
    "CDG": "PAR", "ORY": "PAR",
    # Germany
    "FRA": "FRA", "MUC": "MUC", "BER": "BER", "HAM": "HAM",
    # Netherlands / Belgium
    "AMS": "AMS", "BRU": "BRU",
    # Switzerland / Austria
    "ZRH": "ZRH", "GVA": "GVA", "VIE": "VIE",
    # Spain
    "MAD": "MAD", "BCN": "BCN", "AGP": "AGP", "SVQ": "SVQ",
    # Portugal
    "LIS": "LIS", "OPO": "OPO",
    # Italy
    "FCO": "ROM", "MXP": "MIL", "VCE": "VCE",
    # Nordics
    "ARN": "STO", "OSL": "OSL", "CPH": "CPH", "HEL": "HEL",
    # Asia-Pacific
    "HKG": "HKG",
    "NRT": "TYO", "HND": "TYO",
    "PVG": "SHA", "PEK": "BJS",
    "SIN": "SIN", "ICN": "SEL", "TPE": "TPE",
    "BKK": "BKK", "KUL": "KUL",
    # Middle East
    "DXB": "DXB", "DOH": "DOH", "AUH": "AUH",
    # Americas
    "JFK": "NYC", "EWR": "NYC", "LGA": "NYC",
    "LAX": "LAX", "SFO": "SFO", "ORD": "CHI", "MIA": "MIA",
    "YYZ": "YTO", "YVR": "YVR",
    # Australia
    "SYD": "SYD", "MEL": "MEL",
}

AIRLINE_NAMES: Dict[str, str] = {
    "IB": "Iberia", "AF": "Air France", "TP": "TAP Portugal",
    "LH": "Lufthansa", "U2": "easyJet", "FR": "Ryanair",
    "VY": "Vueling", "BA": "British Airways", "EI": "Aer Lingus",
    "KL": "KLM", "SN": "Brussels Airlines", "AZ": "ITA Airways",
    "W6": "Wizz Air", "PC": "Pegasus Airlines", "HV": "Transavia",
    "TO": "Transavia France", "D8": "Norwegian", "SK": "SAS",
    "AY": "Finnair", "OS": "Austrian Airlines", "LX": "Swiss",
    "TK": "Turkish Airlines", "EK": "Emirates", "QR": "Qatar Airways",
    "SQ": "Singapore Airlines", "CX": "Cathay Pacific",
    "MH": "Malaysia Airlines", "TG": "Thai Airways",
    "JL": "Japan Airlines", "NH": "ANA", "OZ": "Asiana",
}

EQUIPMENT_FEES: Dict[str, float] = {
    "skis": 50.0, "snowboard": 50.0, "surfboard": 70.0,
}


def _to_city(iata: str) -> str:
    """Convert airport IATA to Travelpayouts city code (falls back to the IATA itself)."""
    return AIRPORT_TO_CITY.get(iata.upper(), iata.upper())


def _booking_link(origin: str, dest: str, date_str: str, marker: Optional[str]) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        date_part = d.strftime("%d%m")
    except ValueError:
        date_part = "0101"
    marker_suffix = f"?marker={marker}" if marker else ""
    return f"https://www.aviasales.com/search/{origin.upper()}{date_part}{dest.upper()}1{marker_suffix}"


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
        adults: int = 1,
    ) -> List[Dict[str, Any]]:
        equip_fee = EQUIPMENT_FEES.get((equipment_type or "").lower(), 0.0)
        all_offers: List[Dict[str, Any]] = []

        for dest_iata in destination_iata_list[:3]:
            offers = await self._search_route(origin_iata, dest_iata, date, equip_fee)
            all_offers.extend(offers)

        return all_offers

    async def _search_route(
        self, origin_iata: str, dest_iata: str, date: str, equip_fee: float
    ) -> List[Dict[str, Any]]:
        # 1. Try exact-date cache (includes airline code when data exists)
        offers = await self._prices_for_dates(origin_iata, dest_iata, date, equip_fee)
        if offers:
            return offers

        # 2. Fall back to city-code month matrix (best coverage)
        origin_city = _to_city(origin_iata)
        dest_city   = _to_city(dest_iata)
        offers = await self._month_matrix(origin_city, dest_city, dest_iata, date, equip_fee)
        return offers

    async def _prices_for_dates(
        self, origin: str, dest: str, date: str, equip_fee: float
    ) -> List[Dict[str, Any]]:
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
            return [self._normalize_v3(item, dest, equip_fee) for item in items]
        except Exception as e:
            print(f"[AVIASALES] prices_for_dates error: {e}")
            return []

    async def _month_matrix(
        self,
        origin_city: str,
        dest_city: str,
        dest_iata: str,
        date: str,
        equip_fee: float,
    ) -> List[Dict[str, Any]]:
        try:
            month = date[:7]
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{TRAVELPAYOUTS_BASE}/v2/prices/month-matrix",
                    params={
                        "origin": origin_city,
                        "destination": dest_city,
                        "currency": "eur",
                        "token": self.token,
                        "month": month,
                        "show_to_affiliates": "true",
                    },
                )
                if resp.status_code != 200:
                    return []
                items = resp.json().get("data", [])

            if not items:
                return []

            # Sort by proximity to requested date, take closest 3
            target = datetime.strptime(date, "%Y-%m-%d")
            items.sort(key=lambda x: abs(
                (datetime.strptime(x["depart_date"], "%Y-%m-%d") - target).days
            ))
            closest = items[:3]

            return [self._normalize_matrix(item, origin_city, dest_iata, equip_fee) for item in closest]
        except Exception as e:
            print(f"[AVIASALES] month_matrix error: {e}")
            return []

    def _normalize_v3(self, item: Dict, dest_iata: str, equip_fee: float) -> Dict[str, Any]:
        origin  = item.get("origin", "")
        dest    = item.get("destination_airport") or item.get("destination", dest_iata)
        dep_at  = item.get("departure_at", "")
        dep_date = dep_at[:10] if dep_at else ""
        airline_code = item.get("airline", "")
        airline_name = AIRLINE_NAMES.get(airline_code, airline_code) or "See booking link"

        raw_link = item.get("link", "")
        if raw_link:
            marker_suffix = f"&marker={self.marker}" if self.marker else ""
            link = f"https://www.aviasales.com{raw_link}{marker_suffix}"
        else:
            link = _booking_link(origin, dest, dep_date, self.marker)

        return {
            "flight_id": f"aviasales-{origin}-{dest}-{dep_date}-{airline_code}",
            "airline": airline_name,
            "origin": origin.upper(),
            "destination": dest.upper(),
            "departure_time": dep_at,
            "arrival_time": "",
            "stops": item.get("transfers", 0),
            "price_eur": float(item.get("price", 0)),
            "baggage_allowance": "Check airline website",
            "equipment_fee_eur": equip_fee,
            "booking_link": link,
        }

    def _normalize_matrix(
        self, item: Dict, origin_city: str, dest_iata: str, equip_fee: float
    ) -> Dict[str, Any]:
        depart_date = item.get("depart_date", "")
        dest_display = dest_iata.upper()

        return {
            "flight_id": f"aviasales-{origin_city}-{dest_iata}-{depart_date}",
            "airline": item.get("gate") or "Best price found",
            "origin": origin_city.upper(),
            "destination": dest_display,
            "departure_time": depart_date,
            "arrival_time": "",
            "stops": item.get("number_of_changes", 0),
            "price_eur": float(item.get("value", 0)),
            "baggage_allowance": "Check airline website",
            "equipment_fee_eur": equip_fee,
            "booking_link": _booking_link(origin_city, dest_iata, depart_date, self.marker),
        }
