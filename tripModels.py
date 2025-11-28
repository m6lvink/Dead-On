from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TripRequest:
    startStation: str
    totalBudgetYen: int
    timeWindowHours: float
    moodLabel: str
    avoidPlaces: List[str]
    userLanguage: str

@dataclass
class POIInfo:
    poiName: str
    poiType: str
    descriptionEn: Optional[str] = None
    descriptionJp: Optional[str] = None

@dataclass
class StationInfo:
    stationName: str
    linkedStations: List[str]
    approxRoundTripCost: int
    approxTravelMinutesTotal: int
    poiList: List[POIInfo]

@dataclass
class ActivityDetail:
    poiName: str
    descriptionEn: str
    descriptionJp: str

@dataclass
class StopDetail:
    stationName: str
    activities: List[ActivityDetail]

@dataclass
class ItineraryOption:
    label: str
    stops: List[StopDetail]
    estimatedTotalCostYen: int
    estimatedTotalTimeMinutes: int

@dataclass
class ItineraryResponse:
    itineraries: List[ItineraryOption]