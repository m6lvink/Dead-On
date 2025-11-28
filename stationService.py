import json
import math
import os
from typing import Dict, List, Optional, Tuple
from tripModels import StationRecord

# Global storage
stationMap = dict()

def loadStationData():
    # Helper to load data once
    if os.path.exists("stations.json"):
        with open("stations.json", "r", encoding="utf-8") as file:
            dataList = json.load(file)
            
        for group in dataList:
            stationList = group.get("stations", [])
            for sData in stationList:
                name = sData.get("name_kanji", "")
                lat = sData.get("lat")
                lon = sData.get("lon")
                pref = sData.get("prefecture", "")
                
                # Validation
                isInvalid = (name == "") or (lat is None) or (lon is None)
                if isInvalid:
                    continue
                
                # Create Record
                record = StationRecord(
                    name=name,
                    latitude=float(lat),
                    longitude=float(lon),
                    prefectureCode=pref
                )
                
                # Store in Dictionary
                stationMap[name] = record

# Initialize on load
loadStationData()

def getStationByName(name: str) -> Optional[StationRecord]:
    if name in stationMap:
        return stationMap[name]
    return None

def calculateDistanceKm(latOne: float, lonOne: float, latTwo: float, lonTwo: float) -> float:
    # Haversine formula
    earthRadiusKm = 6371.0
    
    latOneRad = math.radians(latOne)
    latTwoRad = math.radians(latTwo)
    deltaLat = math.radians(latTwo - latOne)
    deltaLon = math.radians(lonTwo - lonOne)
    
    valA = math.sin(deltaLat / 2) ** 2 + math.cos(latOneRad) * math.cos(latTwoRad) * math.sin(deltaLon / 2) ** 2
    valC = 2 * math.atan2(math.sqrt(valA), math.sqrt(1 - valA))
    
    return earthRadiusKm * valC

def findNearbyStations(startStation: StationRecord, maxDistanceKm: float) -> List[str]:
    # Returns a list of station names within the radius
    nearbyNames = list()
    
    for record in stationMap.values():
        if record.name == startStation.name:
            continue
            
        # Coord diff before relying on math
        latDiff = abs(record.latitude - startStation.latitude)
        if latDiff > 1.0: # Approx 111km
            continue
            
        dist = calculateDistanceKm(
            startStation.latitude, 
            startStation.longitude, 
            record.latitude, 
            record.longitude
        )
        
        isWithinRange = (dist <= maxDistanceKm) and (dist > 2.0) # Ensure not too close
        if isWithinRange:
            nearbyNames.append(record.name)
            
    return nearbyNames