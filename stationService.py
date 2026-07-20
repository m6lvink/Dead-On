import json
import math
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
from tripModels import StationRecord

# Configure logging
logger = logging.getLogger(__name__)

# Global storage
stationMap = dict()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Same-spot threshold for duplicate name_kanji entries (degrees)
SAME_LOCATION_DEG = 0.001
# ~111 km per degree latitude
KM_PER_DEG_LAT = 111.0


def validateStationData(sData: dict) -> bool:
    """
    Validate station record structure and data types.
    Ensures data integrity before creating StationRecord.
    """
    # Check required fields exist
    required_fields = ['name_kanji', 'lat', 'lon']
    for field in required_fields:
        if field not in sData:
            return False

    # Validate name_kanji is non-empty string
    name = sData.get('name_kanji')
    if not isinstance(name, str) or not name.strip():
        return False

    # Validate latitude and longitude are valid numbers
    try:
        lat = float(sData['lat'])
        lon = float(sData['lon'])

        # Validate coordinate ranges
        # Latitude: -90 to 90
        # Longitude: -180 to 180
        if not (-90.0 <= lat <= 90.0):
            return False
        if not (-180.0 <= lon <= 180.0):
            return False

    except (TypeError, ValueError):
        return False

    # Validate prefecture is a string (optional field)
    pref = sData.get('prefecture', '')
    if not isinstance(pref, str):
        return False

    return True


def _isSameLocation(latOne: float, lonOne: float, latTwo: float, lonTwo: float) -> bool:
    return (
        abs(latOne - latTwo) < SAME_LOCATION_DEG
        and abs(lonOne - lonTwo) < SAME_LOCATION_DEG
    )


def loadStationData():
    """
    Load station data from stations.json with schema validation.
    Invalid records are skipped.
    """
    stationDataPath = os.path.join(BASE_DIR, "stations.json")

    if not os.path.exists(stationDataPath):
        logger.warning("stations.json not found. Station lookup disabled.")
        return

    try:
        with open(stationDataPath, "r", encoding="utf-8") as file:
            dataList = json.load(file)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse stations.json: {e}")
        return
    except Exception as e:
        logger.error(f"Failed to load stations.json: {e}")
        return

    valid_count = 0
    invalid_count = 0
    duplicate_same_count = 0
    duplicate_distant_count = 0

    # Validate dataList is a list
    if not isinstance(dataList, list):
        logger.error("stations.json must contain a list of station groups")
        return

    for group in dataList:
        # Validate group is a dictionary
        if not isinstance(group, dict):
            invalid_count += 1
            continue

        stationList = group.get("stations", [])

        # Validate stationList is a list
        if not isinstance(stationList, list):
            invalid_count += 1
            continue

        for sData in stationList:
            # Validate sData is a dictionary
            if not isinstance(sData, dict):
                invalid_count += 1
                continue

            # Validate station data schema
            if not validateStationData(sData):
                invalid_count += 1
                continue

            # Create Record with validated data
            try:
                record = StationRecord(
                    name=sData["name_kanji"],
                    latitude=float(sData["lat"]),
                    longitude=float(sData["lon"]),
                    prefectureCode=sData.get("prefecture", "")
                )

                existing = stationMap.get(record.name)
                if existing is not None:
                    # Same spot on another line --> keep first entry
                    if _isSameLocation(
                        existing.latitude,
                        existing.longitude,
                        record.latitude,
                        record.longitude,
                    ):
                        duplicate_same_count += 1
                        continue
                    # Same name in a different city --> keep first-loaded (stable)
                    logger.debug(
                        f"Skipping distant duplicate station name: {record.name}"
                    )
                    duplicate_distant_count += 1
                    continue

                stationMap[record.name] = record
                valid_count += 1
            except Exception as e:
                logger.debug(f"Failed to create StationRecord: {e}")
                invalid_count += 1

    logger.info(
        f"Loaded {valid_count} stations "
        f"({invalid_count} invalid, "
        f"{duplicate_same_count} same-location dupes, "
        f"{duplicate_distant_count} distant name collisions skipped)"
    )


# Initialize on load
loadStationData()


def getStationByName(name: str) -> Optional[StationRecord]:
    """Retrieve a station record by name."""
    if name in stationMap:
        return stationMap[name]
    return None


def calculateDistanceKm(latOne: float, lonOne: float, latTwo: float, lonTwo: float) -> float:
    """
    Calculate distance between two coordinates using Haversine formula.
    Returns distance in kilometers.
    """
    earthRadiusKm = 6371.0

    latOneRad = math.radians(latOne)
    latTwoRad = math.radians(latTwo)
    deltaLat = math.radians(latTwo - latOne)
    deltaLon = math.radians(lonTwo - lonOne)

    valA = math.sin(deltaLat / 2) ** 2 + math.cos(latOneRad) * math.cos(latTwoRad) * math.sin(deltaLon / 2) ** 2
    valC = 2 * math.atan2(math.sqrt(valA), math.sqrt(1 - valA))

    return earthRadiusKm * valC


def _degreeBounds(maxDistanceKm: float, latitude: float) -> Tuple[float, float]:
    """
    Lat/lon degree thresholds for a quick box filter before Haversine.
    Pads the search radius so edge stations are not dropped early.
    """
    paddedKm = max(maxDistanceKm * 1.2, maxDistanceKm + 1.0)
    latBound = paddedKm / KM_PER_DEG_LAT
    cosLat = math.cos(math.radians(latitude))
    # Avoid division by near-zero near the poles
    if abs(cosLat) < 0.01:
        lonBound = 180.0
    else:
        lonBound = paddedKm / (KM_PER_DEG_LAT * abs(cosLat))
    return latBound, lonBound


def findNearbyStations(startStation: StationRecord, maxDistanceKm: float) -> List[str]:
    """
    Returns a list of station names within the specified radius.
    For radii above 2.0 km, filters out stations that are too close (< 2.0 km).
    For smaller radii (e.g. walking 1.5 km), only the start station is excluded.
    """
    nearbyNames = list()

    # Small radius (walking) --> no 2 km floor, otherwise nothing can match
    minDistanceKm = 0.0 if maxDistanceKm <= 2.0 else 2.0
    latBound, lonBound = _degreeBounds(maxDistanceKm, startStation.latitude)

    for record in stationMap.values():
        if record.name == startStation.name:
            continue

        # Quick coordinate diff check before expensive math
        latDiff = abs(record.latitude - startStation.latitude)
        if latDiff > latBound:
            continue

        lonDiff = abs(record.longitude - startStation.longitude)
        if lonDiff > lonBound:
            continue

        dist = calculateDistanceKm(
            startStation.latitude,
            startStation.longitude,
            record.latitude,
            record.longitude
        )

        # Ensure not too close (when radius allows a 2 km floor)
        isWithinRange = (dist <= maxDistanceKm) and (dist > minDistanceKm)
        if isWithinRange:
            nearbyNames.append(record.name)

    return nearbyNames
