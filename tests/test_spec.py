from __future__ import annotations
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class BuildingSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spec=json.loads((ROOT/"spec/building.json").read_text(encoding="utf-8"))
    def test_positive_dimensions(self):
        s=self.spec;self.assertGreater(s["storeys"],0);self.assertGreater(s["floor_height_m"],0);self.assertGreater(s["footprint"]["width_m"],0);self.assertGreater(s["footprint"]["depth_m"],0)
    def test_concept_area(self):
        s=self.spec;self.assertEqual(s["storeys"]*s["footprint"]["width_m"]*s["footprint"]["depth_m"],2592.0)
    def test_pv_count(self):
        pv=self.spec["pv"];self.assertEqual(pv["rows"]*pv["columns"],32)
if __name__=="__main__":unittest.main()
