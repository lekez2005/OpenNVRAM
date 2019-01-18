#!/usr/bin/env python3
"""
Run a regression test on mux array and a horizontal casecade of decoder, address mux and wordline driver in order
"""
from cam_test_base import CamTestBase
from globals import OPTS
from unittest import skipIf

CamTestBase.initialize_tests(CamTestBase.config_template)

import debug
from base import design
import numpy as np


class DecoderMuxDriverCascade(design.design):
    """
    Creates cascade of decoder, mux and wordline driver
    """
    def __init__(self, rows, cols=8):
        design.design.__init__(self, "address_mux_cascade")
        debug.info(1, "Creating {0}".format(self.name))

        from modules.cam import address_mux_array
        from modules import hierarchical_decoder
        from modules import wordline_driver

        from base.vector import vector

        self.add_pin_list(["vdd", "gnd"])

        decoder = hierarchical_decoder.hierarchical_decoder(rows)
        self.add_mod(decoder)

        driver = wordline_driver.wordline_driver(rows, cols)
        self.add_mod(driver)

        mux_array = address_mux_array.address_mux_array(rows)
        self.add_mod(mux_array)

        # add decoder
        decoder_offset = vector(0, -decoder.predecoder_height)
        decoder_inst = self.add_inst("decoder", decoder, offset=decoder_offset)
        args = []
        for addr_bit in range(int(np.log2(rows))):
            args.append("A[{0}]".format(addr_bit))
        for row in range(rows):
            args.append("decode[{0}]".format(row))
        args.extend(["clk", "vdd", "gnd"])
        self.connect_inst(args)

        # address_mux
        mux_offset = vector(decoder.row_decoder_width, 0)
        self.add_inst("mux_array", mux_array, offset=mux_offset)
        args = []
        for row in range(rows):
            args.append("dec[{0}]".format(row))
            args.append("tag[{0}]".format(row))
            args.append("mux_out[{0}]".format(row))
        args.extend(["sel", "sel_bar", "sel_all", "sel_all_bar", "vdd", "gnd"])
        self.connect_inst(args)

        # wordline driver
        driver_offset = mux_offset + vector(mux_array.width, 0)
        self.add_inst("wordline_driver", driver, offset=driver_offset)
        args = []
        for row in range(rows):
            args.append("wl_in[{0}]".format(row))
        for row in range(rows):
            args.append("wl[{0}]".format(row))
        args.extend(["driver_en", "vdd", "gnd"])
        self.connect_inst(args)

        self.copy_layout_pin(decoder_inst, "vdd", "vdd")
        self.copy_layout_pin(decoder_inst, "gnd", "gnd")


class DecoderMuxDriverCascadeTest(CamTestBase):

    def setUp(self):
        super(DecoderMuxDriverCascadeTest, self).setUp()
        import tech
        tech.drc_exceptions["hierarchical_decoder"] = tech.drc_exceptions["latchup"] + tech.drc_exceptions["min_nwell"]
        tech.drc_exceptions["hierarchical_decoder"] = tech.drc_exceptions["latchup"] + tech.drc_exceptions["min_nwell"]
        tech.drc_exceptions["wordline_driver"] = tech.drc_exceptions["latchup"] + tech.drc_exceptions["min_nwell"]
        tech.drc_exceptions["wordline_driver"] = tech.drc_exceptions["latchup"] + tech.drc_exceptions["min_nwell"]

    def test_decoder(self):
        from modules import hierarchical_decoder
        debug.info(2, "Checking decoder array")
        decoder = hierarchical_decoder.hierarchical_decoder(16)
        self.local_drc_check(decoder)

    def test_address_mux_array(self):
        from modules.cam import address_mux_array
        debug.info(2, "Checking address mux array")
        mux_array = address_mux_array.address_mux_array(16)
        self.local_check(mux_array)

    def test_wordline_driver_array(self):
        from modules.wordline_driver import wordline_driver
        driver = wordline_driver(16, no_cols=8)
        debug.info(2, "Checking wordline driver array")
        self.local_drc_check(driver)

    def test_cascade_2x4_predecode(self):
        debug.info(2, "Checking cascade with 2x4 predecode")
        cascade = DecoderMuxDriverCascade(16, 8)
        self.local_check(cascade)

    def test_cascade_3x8_predecode(self):
        debug.info(2, "Checking cascade with 3x8 predecode")
        cascade = DecoderMuxDriverCascade(32, 8)
        self.local_check(cascade)


CamTestBase.run_tests(__name__)
