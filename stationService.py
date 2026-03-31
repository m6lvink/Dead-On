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


def loadStationData():
    """
    Load station data from stations.json with schema validation.
    Invalid records are skipped.
    """
    if not os.path.exists("stations.json"):
        logger.warning("stations.json not found. Station lookup disabled.")
        return
        
    try:
        with open("stations.json", "r", encoding="utf-8") as file:
            dataList = json.load(file)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse stations.json: {e}")
        return
    except Exception as e:
        logger.error(f"Failed to load stations.json: {e}")
        return
    
    valid_count = 0
    invalid_count = 0
    
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
                stationMap[record.name] = record
                valid_count += 1
            except Exception as e:
                logger.debug(f"Failed to create StationRecord: {e}")
                invalid_count += 1
    
    logger.info(f"Loaded {valid_count} stations ({invalid_count} invalid records skipped)")


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


def findNearbyStations(startStation: StationRecord, maxDistanceKm: float) -> List[str]:
    """
    Returns a list of station names within the specified radius.
    Filters out stations that are too close (< 2.0 km).
    """
    nearbyNames = list()
    
    for record in stationMap.values():
        if record.name == startStation.name:
            continue
            
        # Quick coordinate diff check before expensive math
        latDiff = abs(record.latitude - startStation.latitude)
        if latDiff > 1.0:  # Approx 111km
            continue
            
        dist = calculateDistanceKm(
            startStation.latitude, 
            startStation.longitude, 
            record.latitude, 
            record.longitude
        )
        
        isWithinRange = (dist <= maxDistanceKm) and (dist > 2.0)  # Ensure not too close
        if isWithinRange:
            nearbyNames.append(record.name)
            
    return nearbyNames
