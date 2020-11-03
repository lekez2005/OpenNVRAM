#!/usr/bin/env python3
"""
Run regression tests on a parameterized inverter for push rule inverters
"""
from test_base import TestBase


class PinvTest(TestBase):

    def test_1_finger_pinv(self):
        import debug
        from modules.push_rules.pinv_horizontal import pinv_horizontal

        debug.info(2, "Checking 1x size inverter")
        inv = pinv_horizontal(size=1)
        self.add_body_tap_and_test(inv)

    def test_two_finger_pinv(self):
        import debug
        from modules.push_rules.pinv_horizontal import pinv_horizontal

        debug.info(2, "Checking two-finger inverter")
        inv = pinv_horizontal(size=2)
        self.add_body_tap_and_test(inv)

    def test_three_finger_pinv(self):
        import debug
        from modules.push_rules.pinv_horizontal import pinv_horizontal

        debug.info(2, "Checking three-finger inverter")
        inv = pinv_horizontal(size=3)
        self.add_body_tap_and_test(inv)

    def test_medium_three(self):
        import debug
        from modules.push_rules.pinv_horizontal import pinv_horizontal

        debug.info(2, "Checking three-finger inverter")
        inv = pinv_horizontal(size=3 * 2)
        self.add_body_tap_and_test(inv)

        debug.info(2, "Checking three-finger inverter")
        inv = pinv_horizontal(size=3 * 4)
        self.add_body_tap_and_test(inv)

    @staticmethod
    def get_max_size():
        from tech import drc, parameter
        from modules.push_rules.pinv_horizontal import pinv_horizontal

        beta = parameter["beta"]
        num_fingers = pinv_horizontal.max_tx_mults
        return num_fingers * drc["maxwidth_tx"] / (beta * drc["minwidth_tx"]), beta

    def test_two_instances(self):
        import debug
        from modules.push_rules.pinv_horizontal import pinv_horizontal

        max_size, beta = self.get_max_size()

        debug.info(2, "Checking two-instance inverter")
        inv = pinv_horizontal(size=max_size * 1.5, beta=beta)
        self.add_body_tap_and_test(inv)

    def test_three_instances(self):
        import debug
        from modules.push_rules.pinv_horizontal import pinv_horizontal

        max_size, beta = self.get_max_size()

        debug.info(2, "Checking three-instance inverter")
        inv = pinv_horizontal(size=max_size * 2.5, beta=beta)
        self.add_body_tap_and_test(inv)


PinvTest.run_tests(__name__)
