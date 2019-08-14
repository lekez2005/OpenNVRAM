import os

import tech
from base import utils
from characterizer.stimuli import stimuli
from globals import OPTS
from modules.bitline_compute.bl_bank import BlBank


class SpiceDut(stimuli):
    """
    Instantiates the sram
    External peripheral spice should also be instantiated here
    """
    baseline = False

    def inst_sram(self, abits, dbits, sram_name):
        self.sf.write("Xsram ")
        for i in range(dbits):
            self.sf.write("D[{0}] ".format(i))
            self.sf.write("mask[{0}] ".format(i))
        for i in range(abits):
            self.sf.write("A[{0}] ".format(i))
            if not self.baseline:
                self.sf.write("A_1[{0}] ".format(i))

        if not self.baseline:
            self.sf.write(" en_0 en_1 sense_amp_ref ")

        self.sf.write(" read ")
        self.sf.write("{0} ".format(tech.spice["clk"]))

        self.sf.write("{0} {1} ".format(self.vdd_name, self.gnd_name))

        if OPTS.separate_vdd:
            self.sf.write(" ".join(BlBank.external_vdds))

        self.sf.write(" {0}\n".format(sram_name))

    def write_include(self, circuit):
        """Include exported spice from cadence"""
        super().write_include(circuit)

    def write_supply(self):
        """ Writes supply voltage statements """
        self.sf.write("V{0} {0} 0 {1}\n".format(self.vdd_name, self.voltage))
        self.sf.write("V{0} 0 {0} {1}\n".format(self.gnd_name, 0))

        # This is for the test power supply
        self.sf.write("V{0} {0} 0 {1}\n".format("test" + self.vdd_name, self.voltage))
        self.sf.write("V{0} {0} 0 {1}\n".format("test" + self.gnd_name, 0))

        if hasattr(OPTS, 'separate_vdd') and OPTS.separate_vdd:
            for vdd_name in BlBank.external_vdds:
                self.gen_constant(vdd_name, self.voltage, gnd_node="gnd")
