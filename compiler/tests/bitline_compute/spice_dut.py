import os

import tech
from characterizer.stimuli import stimuli
from globals import OPTS
from modules.bitline_compute.bl_bank import BlBank


class SpiceDut(stimuli):
    """
    Instantiates the sram
    External peripheral spice should also be instantiated here
    """
    words_per_row = 1

    def inst_sram(self, abits, dbits, sram_name):
        self.sf.write("Xsram ")

        if OPTS.baseline:
            for i in range(dbits):
                self.sf.write("D[{0}] ".format(i))
                self.sf.write("mask[{0}] ".format(i))
            for i in range(abits):
                self.sf.write("A[{0}] ".format(i))
            self.sf.write(" read ")
            self.sf.write("{0} ".format(tech.spice["clk"]))
            if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
                self.sf.write(" {0} {0} {1} ".format(self.vdd_name, self.gnd_name))
            else:
                self.sf.write(" bank_sel sense_trig {0} {1} ".format(self.vdd_name, self.gnd_name))

        else:
            for i in range(dbits):
                self.sf.write("D[{0}] ".format(i))
                self.sf.write("mask[{0}] ".format(i))

            for i in range(dbits):
                self.sf.write("bus[{0}] ".format(i))

            for i in range(abits):
                self.sf.write("A[{0}] ".format(i))
                self.sf.write("A_1[{0}] ".format(i))

            if OPTS.serial:
                for col in range(dbits):
                    # self.sf.write(" c_val[{0}] cin[{0}] cout[{0}] ".format(col))
                    self.sf.write(" c_val[{0}] ".format(col))
            else:
                for word in range(self.words_per_row):
                    self.sf.write(" cin[{0}] cout[{0}] ".format(word))

            self.sf.write(" en_0 en_1 sense_amp_ref ")

            if OPTS.serial:
                self.sf.write(" s_and s_nand s_or s_nor s_xor s_xnor s_sum s_data s_cout "
                              "s_mask_in s_bus ")
                if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
                    self.sf.write(" read bank_sel mask_en sr_en ")
                else:
                    self.sf.write(" read bank_sel sense_trig diff diffb  mask_en sr_en ")
            else:
                self.sf.write(" s_and s_nand s_or s_nor s_xor s_xnor s_sum s_data "
                              "s_mask_in s_bus s_shift s_sr s_lsb s_msb ")
                if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
                    self.sf.write(" read bank_sel sr_en ")
                else:
                    self.sf.write(" read bank_sel sense_trig diff diffb sr_en ")
            self.sf.write("{0} ".format(tech.spice["clk"]))

            self.sf.write("{0} {1} ".format(self.vdd_name, self.gnd_name))

            for col in range(dbits):
                self.sf.write(" and[{}] ".format(col))
                self.sf.write(" nor[{}] ".format(col))

        if OPTS.separate_vdd:
            self.sf.write(" ".join(BlBank.external_vdds))

        self.sf.write(" {0}\n".format(sram_name))

    def write_include(self, circuit):
        """Include exported spice from cadence"""
        super().write_include(circuit)

    @staticmethod
    def replace_pex_subcells():
        if OPTS.use_pex and not OPTS.top_level_pex:
            pex_file = OPTS.pex_spice
            original_netlist = OPTS.spice_file
            module_names = [x.name for x in OPTS.pex_submodules]
            module_name = ""
            in_subcell = False
            with open(original_netlist, 'r') as original, open(pex_file, 'w') as pex:
                for line in original:
                    if line.startswith('.SUBCKT'):
                        module_name = line.split()[1]
                        if module_name in module_names:
                            in_subcell = True
                        else:
                            pex.write(line)
                    elif line.startswith('.ENDS'):
                        if in_subcell:
                            in_subcell = False
                            pex.write('.include {}\n'.format(
                                os.path.join(OPTS.openram_temp, module_name+'_pex.sp')))
                        else:
                            pex.write(line)
                    elif not in_subcell:
                        pex.write(line)
                pex.flush()

    def write_supply(self):
        """ Writes supply voltage statements """
        self.sf.write("V{0} {0} 0 {1}\n".format(self.vdd_name, self.voltage))
        self.sf.write("V{0} 0 {0} {1}\n".format(self.gnd_name, 0))

        # This is for the test power supply
        self.sf.write("V{0} {0} 0 {1}\n".format("test" + self.vdd_name, self.voltage))
        self.sf.write("V{0} {0} 0 {1}\n".format("test" + self.gnd_name, 0))

        if OPTS.separate_vdd:
            for vdd_name in BlBank.external_vdds:
                self.gen_constant(vdd_name, self.voltage, gnd_node="gnd")
