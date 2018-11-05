#!/usr/bin/env python2.7
"""
Run a regresion test on ml precharge array
"""
import sys

from cam_test_base import CamTestBase, run_tests
import globals
args = sys.argv
(OPTS, _) = globals.parse_args()
sys.argv = args
globals.init_openram("config_cam_{}".format(OPTS.tech_name))

import debug
import design
from globals import OPTS
from unittest import skip


class ArrayCascade(design.design):
    """
    Creates cascade of bitcell, precharge and flops
    """
    def __init__(self, rows, ml_size=1):
        design.design.__init__(self, "ml_cascade")
        debug.info(1, "Creating {0}".format(self.name))

        from modules.cam import ml_precharge_array
        from modules.cam import cam_bitcell_array
        from modules.cam import tag_flop_array
        from vector import vector

        self.add_pin_list(["vdd", "gnd"])

        bitcell_array = cam_bitcell_array.cam_bitcell_array(1, rows)
        self.add_mod(bitcell_array)

        ml_array = ml_precharge_array.ml_precharge_array(rows, ml_size)
        self.add_mod(ml_array)

        tag_flops = tag_flop_array.tag_flop_array(rows)
        self.add_mod(tag_flops)

        # add bitcell array
        bitcell_offset = vector(0, 0)
        bitcell_array_inst = self.add_inst("bitcell_array", bitcell_array, offset=bitcell_offset)
        args = ["bl[0]", "br[0]", "sl[0]", "slb[0]"]
        for row in range(rows):
            args.append("wl[{}]".format(row))
            args.append("ml[{}]".format(row))
        args.extend(["vdd", "gnd"])
        self.connect_inst(args)

        # ml precharge
        ml_offset = bitcell_offset + vector(bitcell_array.width, 0)
        self.add_inst("ml_array", ml_array, offset=ml_offset)
        args = ["precharge_bar"]
        args.extend(["ml[{}]".format(row) for row in range(rows)])
        args.append("vdd")
        self.connect_inst(args)

        # tag flops
        tags_offset = ml_offset + vector(ml_array.width, 0)
        tags_inst = self.add_inst("tag_flops", tag_flops, offset=tags_offset)
        args = ["ml[{0}]".format(row) for row in range(rows)]
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


    def test_min_width_cell(self):
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
        self.local_check(cascade, final_verification=False)

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

        self.local_check(cascade, final_verification=False)


run_tests(__name__)
