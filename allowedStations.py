import json
import os
from pathlib import Path

# Resolve stationDataset.json 
currentFilePath = Path(__file__).resolve()
datasetPath = currentFilePath.with_name("stationDataset.json")

if not datasetPath.exists():
    raise FileNotFoundError(f"stationDataset.json not found at: {datasetPath}")

with datasetPath.open(encoding="utf-8") as datasetFile:
    stationDataset = json.load(datasetFile)

# Collect all unique stationName from ds
allowedStationNames = sorted(
    {stationEntry.get("stationName", "").strip()
     for stationEntry in stationDataset
     if stationEntry.get("stationName")}
)

# TODO: Add multiple aliases for same station incase they dont exist in stationDataset.json
