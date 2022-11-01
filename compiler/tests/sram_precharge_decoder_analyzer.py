#!env python3

from testutils import OpenRamTest
from sim_analyzer_test import SimAnalyzerTest
from precharge_decoder_analyzer import PrechargeDecoderAnalyzer


class SramPrechargeDecoderAnalyzer(PrechargeDecoderAnalyzer, SimAnalyzerTest,
                                   OpenRamTest):
    def test_analysis(self):
        self.run_analysis()


if __name__ == "__main__":
    SramPrechargeDecoderAnalyzer.parse_options()
    SramPrechargeDecoderAnalyzer.run_tests(__name__)
