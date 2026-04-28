import unittest
from config import SystemConfig
from components import H2Storage, Electrolyzer, FuelCell, HeatPump, ThermalStorage
from dispatch import _run_electrolyzer, _run_fuel_cell

class TestDispatch(unittest.TestCase):
    def setUp(self):
        self.config = SystemConfig()
        self.h2 = H2Storage(self.config)
        self.ely = Electrolyzer(self.config)
        self.fc = FuelCell(self.config)
        self.hp = HeatPump(self.config)
        self.ts = ThermalStorage(self.config)

    def test_run_electrolyzer(self):
        power, heat, export = _run_electrolyzer(20, 1, self.ely, self.h2)
        self.assertGreaterEqual(power, 0)
        self.assertGreaterEqual(heat, 0)

    def test_run_fuel_cell(self):
        def dummy_should_use_fc(price, shortage, h2, day):
            return True
        power, grid_import, heat = _run_fuel_cell(10, 0.2, 1, 1, self.config, self.h2, self.fc, dummy_should_use_fc)
        self.assertGreaterEqual(power, 0)
        self.assertGreaterEqual(heat, 0)

if __name__ == '__main__':
    unittest.main()
