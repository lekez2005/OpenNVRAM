import numpy as np
import os

import tech
from characterizer.stimuli import stimuli
from globals import OPTS
from modules.shared_decoder.cmos_sram import CmosSram


class SpiceDut(stimuli):
    """
    Instantiates the sram
    External peripheral spice should also be instantiated here
    """

    def instantiate_sram(self, abits, dbits, num_banks, sram_name):
        self.sf.write("Xsram ")
        if OPTS.push:
            num_banks = 1

        for j in range(num_banks):
            for i in range(dbits):
                self.sf.write("D[{0}] ".format(i))
                self.sf.write("mask[{0}] ".format(i))
        actual_a_bits = abits if num_banks == 1 else abits - 1
        for i in range(actual_a_bits):
            self.sf.write("A[{0}] ".format(i))

        # connect bank_sel_2 to last address bit
        if not OPTS.push:
            bank_sel_2 = "A[{0}]".format(abits - 1) * int(num_banks == 2)
        else:
            bank_sel_2 = ""

        self.sf.write(" read {0} bank_sel {1} sense_trig {2} {3} ".
                      format(tech.spice["clk"], bank_sel_2, self.vdd_name,
                             self.gnd_name))
        if OPTS.mram == "sotfet":
            self.sf.write(" vref ")
        elif OPTS.push:
            self.sf.write(" precharge_trig ")

        self.sf.write(" {0}\n".format(sram_name))

        if OPTS.mram == "sotfet":
            self.gen_constant("vref", OPTS.sense_amp_ref, gnd_node="gnd")

    def write_include(self, circuit):
        super().write_include(circuit)

        if OPTS.mram == "sotfet":
            if not OPTS.use_pex:
                self.remove_subckt("sotfet_mram_small",
                                   os.path.join(OPTS.openram_temp, "sram.sp"))
            pins = "BL BR RWL WWL gnd"
            model_file = os.path.join(OPTS.openram_tech, "sp_lib", OPTS.model_file)
            params = {
                "pins": pins,
                "reference_vt": OPTS.reference_vt,
                "ferro_ratio": OPTS.ferro_ratio,
                "g_AD": OPTS.g_AD,
                "gate_res": OPTS.gate_res,
                "h_ext": OPTS.h_ext,
                "llg_prescale": OPTS.llg_prescale,
                "fm_temperature": OPTS.fm_temperature
            }

            model_content = open(model_file, "r").read().format(**params)

            f_name = os.path.join(OPTS.openram_temp, "sotfet_model.scs")
            with open(f_name, "w") as f:
                f.write(model_content)
            self.sf.write(".include \"{0}\"\n".format(f_name))

    def replace_bitcell(self, sram: CmosSram):
        if not OPTS.use_pex:
            return
        if OPTS.mram == "sotfet":
            self.replace_sotfet_cells(sram)

    def replace_sotfet_cells(self, sram: CmosSram):
        f_name = os.path.join(OPTS.openram_temp, "bitcell_fix.sp")
        vgate_tie_count = 0
        with open(f_name, "w") as f:
            for bank in range(sram.num_banks):
                for row in range(sram.bank.num_rows):
                    for col in range(sram.bank.num_cols):
                        # tie vgate to ground
                        vgate_node = "Xsram.Xbank{}_Xbitcell_array_Xbit_r{}" \
                                     "_c{}_vgate_tie_gnd".format(bank, row, col)
                        f.write("r_vgate_tie_{} {} 0 1\n".format(vgate_tie_count, vgate_node))
                        vgate_tie_count += 1

                        # add bitcell
                        bl_node = "Xsram.N_Xbank{0}_bl[{1}]_Xbank{0}_Xbitcell_array_Xbit_" \
                                  "r{2}_c{1}_MM1_d".format(bank, col, row)
                        br_node = "Xsram.N_Xbank{0}_br[{1}]_Xbank{0}_Xbitcell_array_Xbit_" \
                                  "r{2}_c{1}_MM2_s".format(bank, col, row)
                        wwl_node = "Xsram.N_Xbank{0}_wwl[{2}]_Xbank{0}_Xbitcell_array_Xbit_" \
                                   "r{2}_c{1}_MM1_g".format(bank, col, row)
                        rwl_node = "Xsram.N_Xbank{0}_rwl[{2}]_Xbank{0}_Xbitcell_array_Xbit_" \
                                   "r{2}_c{1}_MM0_g".format(bank, col, row)
                        gnd_node = "0"
                        cell_name = OPTS.bitcell_name_template.format(bank=bank, row=row, col=col)
                        f.write("{} {} {} {} {} {} sotfet_mram_small\n".
                                format(cell_name, bl_node, br_node, rwl_node, wwl_node, gnd_node))

        self.sf.write(".include \"{0}\"\n".format(f_name))
