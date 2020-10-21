import os

import tech
from characterizer.stimuli import stimuli
from globals import OPTS
from modules.sotfet.sf_cam import SfCam


class SfCamDut(stimuli):
    is_sotfet = True

    def inst_sram(self, abits, dbits, sram_name):
        self.sf.write("Xsram ")
        for i in range(dbits):
            self.sf.write("data[{0}] ".format(i))
        for i in range(dbits):
            self.sf.write("mask[{0}] ".format(i))
        for i in range(abits):
            self.sf.write("A[{0}] ".format(i))
        for row in range(OPTS.num_words):
            self.sf.write("search_out[{0}] ".format(row))
        self.sf.write(" search search_ref ")
        self.sf.write("{0} bank_sel ".format(tech.spice["clk"]))
        if self.is_sotfet and OPTS.slow_ramp:
            self.sf.write(" vbias_n vbias_p ")
        self.sf.write("{0} {1} ".format(self.vdd_name, self.gnd_name))

        if hasattr(OPTS, 'separate_vdd') and OPTS.separate_vdd:
            self.sf.write("vdd_wordline vdd_decoder vdd_logic_buffers vdd_data_flops vdd_bitline_buffer "
                          "vdd_bitline_logic vdd_sense_amp ")

        self.sf.write("{0}\n".format(sram_name))

        if self.is_sotfet and OPTS.slow_ramp:
            self.gen_constant("vbias_n", OPTS.vbias_n, gnd_node="gnd")
            # add current mirror
            self.sf.write("Xcurrent_mirror vbias_n vbias_p vdd gnd current_mirror \n")
            self.sf.write("Cmirror_cap vbias_p gnd 10p \n")

        self.gen_constant("search_ref", OPTS.search_ref, gnd_node="gnd")

    def write_include(self, circuit):
        if not self.is_sotfet:
            super().write_include(circuit)
        else:
            if OPTS.use_pex:
                replaced_pex = os.path.join(OPTS.openram_temp, "replaced_pex.sp")
                if not os.path.exists(replaced_pex):
                    open(replaced_pex, 'a').close()
                OPTS.replaced_pex = replaced_pex
                super().write_include(replaced_pex)
            else:
                super().write_include(circuit)
        if self.is_sotfet:
            if not OPTS.use_pex:
                self.remove_subckt(OPTS.bitcell,
                                   os.path.join(OPTS.openram_temp, "sram.sp"))
            pins = "BL BR ML WL gnd"

            if OPTS.series:
                i8_nets = "gnd ML BL net29 int mz1"
                i9_nets = "gnd int BR net30 gnd mz2"
            else:
                i8_nets = "gnd ML net29 BL gnd mz1"
                i9_nets = "gnd ML net30 BR gnd mz2"

            model_file = os.path.join(OPTS.openram_tech, "sp_lib", OPTS.model_file)

            # TODO temporary hack to make simulation work on talisman
            if "talisman" in os.getenv("HOST"):
                host_suffix = "_talisman"
            else:
                host_suffix = ""

            params = {
                "cell_name": OPTS.bitcell,
                "pins": pins,
                "i8_nets": i8_nets,
                "i9_nets": i9_nets,
                "reference_vt": OPTS.reference_vt,
                "ferro_ratio": OPTS.ferro_ratio,
                "delta_vt": OPTS.delta_vt,
                "g_AD": OPTS.g_AD,
                "gate_res": OPTS.gate_res,
                "h_ext": OPTS.h_ext,
                "llg_prescale": OPTS.llg_prescale,
                "fm_temperature": OPTS.fm_temperature,
                "host_suffix": host_suffix
            }

            model_content = open(model_file, "r").read().format(**params)

            f_name = os.path.join(OPTS.openram_temp, "sotfet_model.scs")
            with open(f_name, "w") as f:
                f.write(model_content)
            self.sf.write(".include \"{0}\"\n".format(f_name))

            if OPTS.slow_ramp:
                current_mirror_mod = os.path.join(OPTS.openram_tech, "sp_lib", "current_mirror.sp")
                self.sf.write(".include {}\n".format(current_mirror_mod))

    def replace_sotfet_cells(self, sram: SfCam):
        if not self.is_sotfet or not OPTS.use_pex:
            return
        replaced_pex = OPTS.replaced_pex

        num_bitcells = sram.num_banks * sram.bank.num_rows * sram.bank.num_cols

        total_count = num_bitcells * 4
        remove_count = 0
        replace_done = False

        with open(OPTS.pex_spice, "r") as pex_f, open(replaced_pex, "w") as replaced_f:
            removing = False
            for line in pex_f:
                if replace_done:
                    replaced_f.write(line)
                    continue
                if removing and not line.startswith("+"):
                    removing = False
                elif removing:
                    continue

                if line.startswith("XXbank0_Xbitcell_array_Xbit_r"):
                    removing = True
                    remove_count += 1
                    continue

                replaced_f.write(line)

                if remove_count >= total_count:
                    replace_done = True

        f_name = os.path.join(OPTS.openram_temp, "bitcell_fix.sp")

        short_resistor_count = 0

        with open(f_name, "w") as f:
            for bank in range(sram.num_banks):
                for row in range(sram.bank.num_rows):
                    for col in range(sram.bank.num_cols):
                        # add bitcell
                        bl_node = "Xsram.N_Xbank{0}_bl[{1}]_Xbank{0}_Xbitcell_array_Xbit_" \
                                  "r{2}_c{1}_MM0_g".format(bank, col, row)
                        br_node = "Xsram.N_Xbank{0}_br[{1}]_Xbank{0}_Xbitcell_array_Xbit_" \
                                  "r{2}_c{1}_MM1_g".format(bank, col, row)
                        wl_node = "Xsram.N_Xbank{0}_wl[{2}]_Xbank{0}_Xbitcell_array_Xbit_" \
                                  "r{2}_c{1}_MM2_g".format(bank, col, row)
                        ml_node = "Xsram.N_Xbank{0}_ml[{2}]_Xbank{0}_Xbitcell_array_Xbit_" \
                                  "r{2}_c{1}_MM0_d".format(bank, col, row)
                        if OPTS.series:
                            gnd_tx = "MM1_d"
                        else:
                            gnd_tx = "MM1_s"
                        gnd_node = "Xsram.N_gnd_Xbank{0}_Xbitcell_array_Xbit_" \
                                   "r{2}_c{1}_{3}".format(bank, col, row, gnd_tx)

                        cell_name = OPTS.bitcell_name_template.format(bank=bank, row=row, col=col)
                        f.write("{} {} {} {} {} {} {}\n".
                                format(cell_name, bl_node, br_node, ml_node, wl_node,
                                       gnd_node, OPTS.bitcell))

                        # connect sf_gate_1 and sf_gate_2
                        gate_1_net = "Xsram.N_Xbank{bank}_Xbitcell_array_Xbit_r{row}_c{col}_sf_gate_1_" \
                                     "Xbank{bank}_Xbitcell_array_Xbit_r{row}_c{col}_MM2_d". \
                            format(row=row, col=col, bank=bank)
                        gate_2_net = "Xsram.N_Xbank{bank}_Xbitcell_array_Xbit_r{row}_c{col}_sf_gate_2_" \
                                     "Xbank{bank}_Xbitcell_array_Xbit_r{row}_c{col}_MM2@2_s". \
                            format(row=row, col=col, bank=bank)
                        f.write("r_short_{} {} {} 1\n".format(short_resistor_count,
                                                              gate_1_net, cell_name + ".net29"))
                        short_resistor_count += 1
                        f.write("r_short_{} {} {} 1\n".format(short_resistor_count,
                                                              gate_2_net, cell_name + ".net30"))
                        short_resistor_count += 1

                        if not OPTS.energy and (row, col) in OPTS.saved_currents:
                            f.write("simulator lang=spectre\n")
                            f.write("save {}.M0:d\n".format(cell_name))
                            f.write("simulator lang=spice\n")

        self.sf.write(".include \"{0}\"\n".format(f_name))

    def write_supply(self):
        """ Writes supply voltage statements """
        self.sf.write("V{0} {0} 0 {1}\n".format(self.vdd_name, self.voltage))
        self.sf.write("V{0} 0 {0} {1}\n".format(self.gnd_name, 0))
        if hasattr(OPTS, 'separate_vdd') and OPTS.separate_vdd:
            self.gen_constant("vdd_decoder", self.voltage, gnd_node="gnd")
            self.gen_constant("vdd_wordline", self.voltage, gnd_node="gnd")
            self.gen_constant("vdd_logic_buffers", self.voltage, gnd_node="gnd")
            self.gen_constant("vdd_data_flops", self.voltage, gnd_node="gnd")
            self.gen_constant("vdd_bitline_buffer", self.voltage, gnd_node="gnd")
            self.gen_constant("vdd_bitline_logic", self.voltage, gnd_node="gnd")
            self.gen_constant("vdd_sense_amp", self.voltage, gnd_node="gnd")

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
