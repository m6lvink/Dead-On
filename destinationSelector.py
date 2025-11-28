from typing import List
from tripModels import TripRequest, StationInfo

def selectCandidateStations(tripRequest: TripRequest, stationDataset: List[StationInfo]) -> List[StationInfo]:
    maxRoundTripCost = int(tripRequest.totalBudgetYen * 0.7)
    maxTravelMinutes = int(tripRequest.timeWindowHours * 60 * 0.5)
    
    startStationLower = tripRequest.startStation.lower()
    avoidPlacesLower = [place.lower() for place in tripRequest.avoidPlaces]
    
    candidateList = []
    
    for station in stationDataset:
        stationNameLower = station.stationName.lower()
        
        if stationNameLower == startStationLower:
            continue
        
        if station.approxRoundTripCost > maxRoundTripCost:
            continue
        
        if station.approxTravelMinutesTotal > maxTravelMinutes:
            continue
        
        isAvoided = False
        for avoidPlace in avoidPlacesLower:
            if avoidPlace in stationNameLower:
                isAvoided = True
                break
            for poi in station.poiList:
                if avoidPlace in poi.poiName.lower():
                    isAvoided = True
                    break
            if isAvoided:
                break
        
        if isAvoided:
            continue
        
        candidateList.append(station)
    
    return candidateList[:5]