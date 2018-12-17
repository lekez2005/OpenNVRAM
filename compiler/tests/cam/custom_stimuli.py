from characterizer.stimuli import stimuli
from globals import OPTS
import tech


class CustomStimuli(stimuli):
    def inst_sram(self, abits, dbits, sram_name):

        self.sf.write("Xsram ")
        for i in range(dbits):
            self.sf.write("D[{0}] ".format(i))
        for i in range(dbits):
            self.sf.write("mask[{0}] ".format(i))
        for i in range(abits):
            self.sf.write("A[{0}] ".format(i))
        for i in ["CSb", "WEb", "OEb", "SEb", "MWb", "BCASTb", "search_ref"]:
            self.sf.write("{0} ".format(i))
        self.sf.write("{0} ".format(tech.spice["clk"]))
        self.sf.write("{0} {1} ".format(self.vdd_name, self.gnd_name))
        self.sf.write("{0}\n".format(sram_name))

        self.gen_constant("search_ref", OPTS.search_ref)
