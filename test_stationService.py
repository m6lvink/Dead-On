import os
import unittest

import stationService
from tripModels import StationRecord


class CalculateDistanceKmTests(unittest.TestCase):
    def test_haversine_short_distance_is_roughly_correct(self):
        # ~1.11 km north of origin at equator scale (0.01 deg lat)
        dist = stationService.calculateDistanceKm(35.0, 135.0, 35.01, 135.0)
        self.assertGreater(dist, 1.0)
        self.assertLess(dist, 1.3)


class FindNearbyStationsTests(unittest.TestCase):
    def setUp(self):
        self._originalMap = dict(stationService.stationMap)
        stationService.stationMap.clear()

        # Start near Osaka
        self.start = StationRecord("起点", 34.7024, 135.4959, "27")
        # ~1.0 km north (walking range)
        self.nearWalk = StationRecord("近隣", 34.7114, 135.4959, "27")
        # ~3.0 km north (outside walking, inside dinner radius with 2km floor)
        self.midRange = StationRecord("中距離", 34.7294, 135.4959, "27")
        # Far east but same latitude --> dropped by lon prefilter for small radii
        self.farEast = StationRecord("遠隔", 34.7024, 140.0000, "13")

        stationService.stationMap[self.start.name] = self.start
        stationService.stationMap[self.nearWalk.name] = self.nearWalk
        stationService.stationMap[self.midRange.name] = self.midRange
        stationService.stationMap[self.farEast.name] = self.farEast

    def tearDown(self):
        stationService.stationMap.clear()
        stationService.stationMap.update(self._originalMap)

    def test_walking_radius_includes_nearby_station(self):
        names = stationService.findNearbyStations(self.start, 1.5)
        self.assertIn(self.nearWalk.name, names)
        self.assertNotIn(self.midRange.name, names)
        self.assertNotIn(self.start.name, names)

    def test_larger_radius_excludes_stations_under_two_km(self):
        names = stationService.findNearbyStations(self.start, 5.0)
        self.assertNotIn(self.nearWalk.name, names)
        self.assertIn(self.midRange.name, names)

    def test_prefilter_keeps_in_range_station(self):
        names = stationService.findNearbyStations(self.start, 1.5)
        self.assertIn(self.nearWalk.name, names)
        self.assertNotIn(self.farEast.name, names)


class DuplicateNameLoadTests(unittest.TestCase):
    def setUp(self):
        self._originalMap = dict(stationService.stationMap)
        stationService.stationMap.clear()

    def tearDown(self):
        stationService.stationMap.clear()
        stationService.stationMap.update(self._originalMap)

    def test_same_location_duplicate_keeps_first(self):
        first = StationRecord("重複", 35.0, 135.0, "27")
        second = StationRecord("重複", 35.0000005, 135.0000005, "27")
        stationService.stationMap[first.name] = first

        existing = stationService.stationMap.get(second.name)
        self.assertIsNotNone(existing)
        if stationService._isSameLocation(
            existing.latitude, existing.longitude, second.latitude, second.longitude
        ):
            pass  # would skip insert in loadStationData
        else:
            stationService.stationMap[second.name] = second

        kept = stationService.getStationByName("重複")
        self.assertEqual(kept.latitude, first.latitude)
        self.assertEqual(kept.longitude, first.longitude)

    def test_distant_duplicate_does_not_overwrite_first(self):
        first = StationRecord("白石", 43.054715, 141.413612, "01")
        distant = StationRecord("白石", 38.0, 140.0, "04")
        stationService.stationMap[first.name] = first

        existing = stationService.stationMap.get(distant.name)
        if existing is not None and not stationService._isSameLocation(
            existing.latitude, existing.longitude, distant.latitude, distant.longitude
        ):
            # loadStationData keeps first-loaded
            pass
        else:
            stationService.stationMap[distant.name] = distant

        kept = stationService.getStationByName("白石")
        self.assertEqual(kept.prefectureCode, "01")
        self.assertAlmostEqual(kept.latitude, first.latitude)


class StationsJsonSmokeTests(unittest.TestCase):
    def test_stations_json_loaded_when_present(self):
        stationPath = os.path.join(stationService.BASE_DIR, "stations.json")
        if not os.path.exists(stationPath):
            self.skipTest("stations.json not present")
        self.assertGreater(len(stationService.stationMap), 0)


if __name__ == "__main__":
    unittest.main()
