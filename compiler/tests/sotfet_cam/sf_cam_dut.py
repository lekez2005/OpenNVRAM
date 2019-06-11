import os

import tech
from characterizer.stimuli import stimuli
from globals import OPTS


class SfCamDut(stimuli):

    def inst_sram(self, abits, dbits, sram_name):
        self.sf.write("Xsram ")
        for i in range(dbits):
            self.sf.write("data[{0}] ".format(i))
        for i in range(dbits):
            self.sf.write("mask[{0}] ".format(i))
        for i in range(abits):
            self.sf.write("A[{0}] ".format(i))
        self.sf.write(" search search_ref ")
        self.sf.write("{0} ".format(tech.spice["clk"]))
        self.sf.write("{0} {1} ".format(self.vdd_name, self.gnd_name))
        self.sf.write("{0}\n".format(sram_name))

        self.gen_constant("search_ref", OPTS.search_ref, gnd_node="gnd")

    def write_include(self, circuit):
        super().write_include(circuit)
        self.write_sotfet_includes()

    def write_sotfet_includes(self):
        cadence_work_dir = os.environ["SYSTEM_CDS_LIB_DIR"]
        p_to_vg = os.path.join(cadence_work_dir, "spintronics/p_to_ids/va_include/p_to_vg.scs")
        sot_llg = os.path.join(cadence_work_dir, "spintronics/sot_llg/spectre/spectre.scs")
        ahdl_include = os.path.join(cadence_work_dir, "spintronics/p_to_vg/veriloga/veriloga.va")

        self.sf.write("\nsimulator lang=spectre\n")
        self.sf.write('\ninclude "{0}"\ninclude "{1}"\nahdl_include "{2}"\n'.format(p_to_vg, sot_llg, ahdl_include))
        self.sf.write("\nsimulator lang=spice\n")

    def write_supply(self):
        """ Writes supply voltage statements """
        self.sf.write("V{0} {0} 0 {1}\n".format(self.vdd_name, self.voltage))
        self.sf.write("V{0} 0 {0} {1}\n".format(self.gnd_name, 0))

    def gen_meas_power(self, meas_name, t_initial, t_final):
        """ Creates the .meas statement for the measurement of avg power """
        # power mea cmd is different in different spice:
        if OPTS.spice_name == "hspice":
            power_exp = "power"
        else:
            power_exp = "par('(-1*v(" + str(self.vdd_name) + ")*I(v" + str(self.vdd_name) + "))')"
        self.sf.write(".meas tran {0} avg {1} from={2}n to={3}n\n\n".format(meas_name,
                                                                            power_exp,
                                                                            t_initial,
                                                                            t_final))

