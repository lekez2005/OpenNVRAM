#!/usr/bin/env python3
"""
Run a regression test on ml precharge array
"""

from cam_test_base import CamTestBase

CamTestBase.initialize_tests(CamTestBase.config_template)

import debug
from base import design
from globals import OPTS


class ArrayCascade(design.design):
    """
    Creates cascade of bitcell, sense_amp precharge and flops
    """
    def __init__(self, rows, ml_size=1):
        design.design.__init__(self, "ml_cascade")
        debug.info(1, "Creating {0}".format(self.name))

        from modules.cam import ml_precharge_array
        from modules.cam import cam_bitcell_12t_array
        from modules.cam import tag_flop_array
        from modules.cam import search_sense_amp_array
        from base.vector import vector

        self.add_pin_list(["vdd", "gnd"])

        bitcell_array = cam_bitcell_12t_array.cam_bitcell_12t_array(1, rows)
        self.add_mod(bitcell_array)

        ml_array = ml_precharge_array.ml_precharge_array(rows, ml_size)
        self.add_mod(ml_array)

        ml_sense_array = search_sense_amp_array.search_sense_amp_array(rows=rows)
        self.add_mod(ml_sense_array)

        tag_flops = tag_flop_array.tag_flop_array(rows)
        self.add_mod(tag_flops)

        # add bitcell array
        bitcell_offset = vector(0, 0)
        bitcell_array_inst = self.add_inst("bitcell_array", bitcell_array, offset=bitcell_offset)
        args = ["bl[0]", "br[0]", "sl[0]", "slb[0]"]
        for row in range(rows):
            args.append("wl[{}]".format(row))
            args.append("wwl[{}]".format(row))
            args.append("ml[{}]".format(row))
        args.extend(["vdd", "gnd"])
        self.connect_inst(args)

        # ml precharge
        ml_offset = bitcell_offset + vector(bitcell_array.width, 0)
        ml_array_inst = self.add_inst("ml_array", ml_array, offset=ml_offset)
        args = ["precharge_bar"]
        args.extend(["ml[{}]".format(row) for row in range(rows)])
        args.append("vdd")
        self.connect_inst(args)

        # add sense amps
        ml_sense_array_inst = self.add_inst("sense_amp_array", ml_sense_array, offset=ml_array_inst.lr())
        args = []
        for i in range(rows):
            args.append("ml[{0}]".format(i))
        for i in range(rows):
            args.append("search_out[{0}]".format(i))
        args.append("search_en")
        args.append("search_ref")
        args.append("vdd")
        args.append("gnd")
        self.connect_inst(args)

        # tag flops
        self.add_inst("tag_flops", tag_flops, offset=ml_sense_array_inst.lr())
        args = ["search_out[{0}]".format(row) for row in range(rows)]
        for i in range(rows):
            args.append("dout[{0}]".format(i))
            args.append("dout_bar[{0}]".format(i))
        args.extend(["clk", "vdd", "gnd"])
        self.connect_inst(args)

        self.copy_layout_pin(bitcell_array_inst, "vdd", "vdd")
        self.copy_layout_pin(bitcell_array_inst, "gnd", "gnd")


class MlPrechargeArrayTest(CamTestBase):

    def setUp(self):
        super(MlPrechargeArrayTest, self).setUp()
        import tech
        tech.drc_exceptions["matchline_precharge"] = tech.drc_exceptions["latchup"] + tech.drc_exceptions["min_nwell"]
        tech.drc_exceptions["ml_precharge_array"] = tech.drc_exceptions["latchup"] + tech.drc_exceptions["min_nwell"]


    def test_min_width_ml_cell(self):
        from modules.cam import matchline_precharge
        debug.info(2, "Checking matchline precharge cell")
        cell = matchline_precharge.matchline_precharge()
        self.local_drc_check(cell)

    def test_multiple_fingers_cell(self):
        from modules.cam import matchline_precharge
        from tech import parameter
        c = __import__(OPTS.bitcell)
        mod_bitcell = getattr(c, OPTS.bitcell)
        bitcell = mod_bitcell()
        debug.info(2, "Checking matchline precharge cell")
        cell = matchline_precharge.matchline_precharge(size=(1.2*bitcell.height)/parameter["min_tx_size"])
        self.local_drc_check(cell)

    def test_precharge_array(self):
        """Test standalone array for drc issues"""
        from modules.cam import ml_precharge_array
        rows = 16
        debug.info(2, "Checking matchline precharge array with {} rows")
        array = ml_precharge_array.ml_precharge_array(rows=rows, size=3)
        self.local_drc_check(array)


    def test_array_bitcell_flops_single_finger(self):
        """
        Create array of bitcells, ml_precharge and tag flops cascade
        Since the tag flops should contain body contacts, both drc and lvs should pass for the cascade
        """
        cascade = ArrayCascade(8, 1)
        self.local_drc_check(cascade)

    def test_array_bitcell_flops_multi_finger(self):
        """
        Create array of bitcells, ml_precharge and tag flops cascade
        Since the tag flops should contain body contacts, both drc and lvs should pass for the cascade
        """
        from tech import parameter
        c = __import__(OPTS.bitcell)
        mod_bitcell = getattr(c, OPTS.bitcell)
        bitcell = mod_bitcell()
        debug.info(2, "Checking matchline precharge cell")
        size = (1.2 * bitcell.height) / parameter["min_tx_size"]
        cascade = ArrayCascade(8, size)

        self.local_drc_check(cascade)


CamTestBase.run_tests(__name__)
