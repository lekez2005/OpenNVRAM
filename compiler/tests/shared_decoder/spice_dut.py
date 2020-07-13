import tech
from characterizer.stimuli import stimuli


class SpiceDut(stimuli):
    """
    Instantiates the sram
    External peripheral spice should also be instantiated here
    """

    def instantiate_sram(self, abits, dbits, num_banks, sram_name):
        self.sf.write("Xsram ")

        for j in range(num_banks):
            for i in range(dbits):
                self.sf.write("D[{0}] ".format(i))
                self.sf.write("mask[{0}] ".format(i))
        actual_a_bits = abits if num_banks == 1 else abits - 1
        for i in range(actual_a_bits):
            self.sf.write("A[{0}] ".format(i))

        # connect bank_sel_2 to last address bit
        bank_sel_2 = "A[{0}]".format(abits - 1) * int(num_banks == 2)

        self.sf.write(" read {0} bank_sel {1} sense_trig {2} {3} ".
                      format(tech.spice["clk"], bank_sel_2, self.vdd_name,
                             self.gnd_name))

        self.sf.write(" {0}\n".format(sram_name))
