#!/usr/bin/env python3
"""
Run a regression test on a basic array
"""

from cam_test_base import CamTestBase
import debug
from globals import OPTS
from unittest import skipIf


class PredecoderFlops(CamTestBase):

    @skipIf(False, "Temp switch")
    def test_without_flop(self):

        from modules.hierarchical_predecode3x8 import hierarchical_predecode3x8 as pre3x8

        debug.info(2, "Testing 3x8 predecoder without flops")
        decoder = pre3x8(route_top_rail=True, use_flops=False)
        self.local_drc_check(decoder)

    @skipIf(False, "Temp switch")
    def test_with_flop(self):
        from modules.hierarchical_predecode3x8 import hierarchical_predecode3x8 as pre3x8

        debug.info(2, "Testing 3x8 predecoder without flops")
        decoder = pre3x8(route_top_rail=True, use_flops=True)
        self.local_drc_check(decoder)

    def test_regression(self):
        from modules.hierarchical_predecode3x8 import hierarchical_predecode3x8 as pre3x8
        from modules.hierarchical_predecode2x4 import hierarchical_predecode2x4 as pre2x4
        from globals import OPTS

        errors = []

        for module in [pre2x4, pre3x8]:
            decoder = module(route_top_rail=True, use_flops=False)
            debug.info(1, "Testing {} predecoder without flops".format(decoder.name))
            try:
                self.local_check(decoder)
            except Exception as err:
                print(err)
                errors.append("Error: {} Predecoder without flops ".format(decoder.name))

            for vertical in [True, False]:
                if vertical:
                    OPTS.predecoder_flop = "ms_flop"
                    OPTS.predecoder_flop_layout = "v"
                    vertical_str = "vertical"
                else:
                    OPTS.predecoder_flop = "ms_flop_horz_pitch"
                    OPTS.predecoder_flop_layout = "h"
                    vertical_str = "horizontal"
                decoder = module(route_top_rail=True, use_flops=True)
                debug.info(1, "Testing {} {} predecoder with flops".format(vertical_str, decoder.name))
                try:
                    self.local_check(decoder)
                except Exception as err:
                    print(err)
                    errors.append("Error: {} Predecoder {} with flops ".format(vertical_str, decoder.name))
        print("\n".join(errors))

    @skipIf(False, "Temp switch")
    def test_full_decoder_with_flops(self):
        from modules.hierarchical_decoder import hierarchical_decoder
        OPTS.decoder_flops = True
        decoder = hierarchical_decoder(32)
        self.local_drc_check(decoder)


CamTestBase.run_tests(__name__)
