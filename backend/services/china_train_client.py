"""
China high-speed rail (CRH) client.

Currently returns realistic mock data.
Future integration: Trip.com Partner API (https://hd.trip.com/partner/) or
12306-compatible third-party APIs.
"""
from typing import List, Dict, Any, Optional
from backend.database import search_china_trains_mock


class ChinaTrainClient:
    def __init__(self, api_key: Optional[str] = None, affiliate_id: Optional[str] = None):
        self.api_key = api_key
        self.affiliate_id = affiliate_id

    async def search_trains(
        self,
        origin_city: str,
        destination_city: str,
        date: str,
        seat_class: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # TODO: replace with real Trip.com / 12306 API call when credentials available
        return search_china_trains_mock(origin_city, destination_city, date, seat_class)
