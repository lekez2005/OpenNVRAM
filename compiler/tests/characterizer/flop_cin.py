#!/usr/bin/env python3

from char_test_base import CharTestBase
from distributed_load_base import DistributedLoadMixin


class FlopCin(DistributedLoadMixin, CharTestBase):
    instantiate_dummy = True

    def setUp(self):
        super().setUp()
        self.set_cell_mod()

    def set_cell_mod(self):
        from globals import OPTS
        if self.options.cell_mod is not None:
            OPTS.ms_flop_mod = self.options.cell_mod
            if self.options.body_tap is None:
                OPTS.ms_flop_tap_mod = self.options.cell_mod + "_tap"
            else:
                OPTS.ms_flop_tap_mod = self.options.body_tap
        else:
            OPTS.ms_flop_mod = OPTS.ms_flop
            OPTS.ms_flop_tap_mod = None  # use default

    def get_pins(self):
        return ["clk"]

    def get_cell_name(self):
        from globals import OPTS
        return OPTS.ms_flop_mod

    def make_dut(self, num_elements):
        from modules.ms_flop_array import ms_flop_array
        from globals import OPTS

        cols = num_elements

        load = ms_flop_array(columns=cols, word_size=cols, flop_mod=OPTS.ms_flop_mod,
                             flop_tap_name=OPTS.ms_flop_tap_mod, align_bitcell=True)
        return load

    def get_dut_instance_statement(self, pin):

        cols = self.load.original_dut.word_size

        dut_instance = "X4 " + " ".join(["din[{}]".format(x) for x in range(cols)])
        for col in range(cols):
            dut_instance += " dout[{0}] dout_bar[{0}] ".format(col)
        dut_instance += " d vdd gnd {}".format(self.load.name)
        return dut_instance


FlopCin.run_tests(__name__)
