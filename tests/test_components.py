import unittest
from components import H2Storage, Electrolyzer, FuelCell, HeatPump
from config import SystemConfig

class TestComponents(unittest.TestCase):
    def setUp(self):
        self.config = SystemConfig()

    def test_h2storage_charge_discharge(self):
        storage = H2Storage(self.config)
        charged = storage.charge(100)
        self.assertGreaterEqual(charged, 0)
        discharged = storage.discharge(50)
        self.assertGreaterEqual(discharged, 0)

    def test_electrolyzer_run(self):
        ely = Electrolyzer(self.config)
        result = ely.run(10, dt_h=1)
        self.assertIn('power_used', result)
        self.assertIn('h2_produced', result)

    def test_fuelcell_run(self):
        fc = FuelCell(self.config)
        result = fc.run(10, 100, dt_h=1)
        self.assertIn('power_out', result)
        self.assertIn('h2_used', result)

    def test_heatpump_repr(self):
        hp = HeatPump(self.config)
        self.assertIsInstance(repr(hp), str)

if __name__ == '__main__':
    unittest.main()
