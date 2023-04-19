#!env python3

from one_t_one_s_test_base import TestBase
from mram_simulator import MramSimulator
from sim_analyzer_test import SimAnalyzerTest
from precharge_decoder_analyzer import PrechargeDecoderAnalyzer


class MramPrechargeDecoderAnalyzer(PrechargeDecoderAnalyzer, MramSimulator,
                                   SimAnalyzerTest, TestBase):
    @staticmethod
    def get_wordline_enable_names():
        return ["wwl_en", "rwl_en"]

    def get_precharge_bitline_names(self):
        return ["bl"]

    def test_analysis(self):
        self.run_analysis()


if __name__ == "__main__":
    MramPrechargeDecoderAnalyzer.parse_options()
    MramPrechargeDecoderAnalyzer.run_tests(__name__)
