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