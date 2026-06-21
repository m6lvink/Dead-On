from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TripConstraints:
    startStationName: str
    totalBudgetYen: int
    timeWindowHours: float
    moodLabel: str
    userLanguage: str
    isVague: bool

@dataclass
class StationRecord:
    name: str
    latitude: float
    longitude: float
    prefectureCode: str

# FORMATTER MODELS (for messageFormatter.py)

@dataclass
class Activity:
    poiName: str
    descriptionEn: str
    descriptionJp: str

@dataclass
class Stop:
    stationName: str
    activities: List[Activity]

@dataclass
class Itinerary:
    label: str
    stops: List[Stop]
    estimatedTotalCostYen: int
    estimatedTotalTimeMinutes: int

@dataclass
class ItineraryResponse:
    itineraries: List[Itinerary]
