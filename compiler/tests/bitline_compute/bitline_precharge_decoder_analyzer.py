#!env python3

from test_base import TestBase
from bl_simulator import BlSimulator
from precharge_decoder_analyzer import PrechargeDecoderAnalyzer
from sim_analyzer_test import SimAnalyzerTest


class BitlinePrechargeAnalyzer(PrechargeDecoderAnalyzer, BlSimulator,
                               SimAnalyzerTest, TestBase):
    def setUp(self):
        super().setUp()
        self.update_global_opts()

    def should_check_precharge(self, cycle_start):
        from globals import OPTS
        web = self.sim_data.get_binary("Web", from_t=cycle_start)[0]
        en_1 = self.sim_data.get_binary("en_1", from_t=cycle_start)[0]
        if OPTS.sim_rw_only and en_1:
            return False
        return web

    def test_simulation(self):
        self.run_analysis()


if __name__ == "__main__":
    BitlinePrechargeAnalyzer.parse_options()
    BitlinePrechargeAnalyzer.run_tests(__name__)
