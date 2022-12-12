#!env python3

from test_base import TestBase
from sim_analyzer_test import SimAnalyzerTest
from precharge_decoder_analyzer import PrechargeDecoderAnalyzer


class PushSramPrechargeDecoderAnalyzer(PrechargeDecoderAnalyzer, SimAnalyzerTest,
                                       TestBase):
    PUSH_MODE = "push"
    valid_modes = [PUSH_MODE]

    def test_analysis(self):
        self.run_analysis()

    def check_decoder_output(self):
        """Wordline always waits for decoder enable the wordline will always rise after.
         Very slim chance of overwriting existing data"""
        pass


if __name__ == "__main__":
    PushSramPrechargeDecoderAnalyzer.parse_options()
    PushSramPrechargeDecoderAnalyzer.run_tests(__name__)
