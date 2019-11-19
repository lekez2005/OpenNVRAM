import os

import tech
from base import utils
from characterizer.stimuli import stimuli
from globals import OPTS


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
        self.sf.write("{0} ".format(tech.spice["clk"]))
        if self.is_sotfet:
            self.sf.write(" vbias_n vbias_p ")
        self.sf.write("{0} {1} ".format(self.vdd_name, self.gnd_name))

        if hasattr(OPTS, 'separate_vdd') and OPTS.separate_vdd:
            self.sf.write("vdd_wordline vdd_decoder vdd_logic_buffers vdd_data_flops vdd_bitline_buffer "
                          "vdd_bitline_logic vdd_sense_amp ")

        self.sf.write("{0}\n".format(sram_name))

        if self.is_sotfet:
            self.gen_constant("vbias_n", OPTS.vbias_n, gnd_node="gnd")
            # add current mirror
            self.sf.write("Xcurrent_mirror vbias_n vbias_p vdd gnd current_mirror \n")
            self.sf.write("Cmirror_cap vbias_p gnd 10p \n")

        self.gen_constant("search_ref", OPTS.search_ref, gnd_node="gnd")

    def write_include(self, circuit):
        pcam_cell_def = """simulator lang=spice
.SUBCKT sot_cam_cell {pins}
MM0 net29 WL net30 gnd nch_mac l=30n w=200n m=1 nf=1
XI8 gnd ML net29 BL gnd mz1 / sotfet gate_R=1000 tx_l=30n tx_w=200n {sotfet_params}
XI9 gnd ML net30 BR gnd mz2 / sotfet gate_R=1000 tx_l=30n tx_w=200n {sotfet_params}
.ENDS
        """
        scam_cell_def = """simulator lang=spice
.SUBCKT sot_cam_cell {pins}
MM0 net29 WL net30 gnd nch_mac l=30n w=200n m=1 nf=1
XI8 gnd ML BL net29 int mz1 / sotfet gate_R=1000 tx_l=30n tx_w=200n {sotfet_params}
XI9 gnd int BR net30 gnd mz2 / sotfet gate_R=1000 tx_l=30n tx_w=200n {sotfet_params}
.ENDS
        """
        super().write_include(circuit)
        ordered_pin_names = ["BL", "BR", "ML", "WL", "mz1", "gnd"]
        if self.is_sotfet and not OPTS.use_pex:
            # remove empty sotfet model. Empty model is used for lvs and pex (box)
            model_file = os.path.join(OPTS.openram_temp, "sram.sp")
            lines = []
            skip_next = False
            with open(model_file, 'r') as f:
                for line in  f.readlines():
                    if ".SUBCKT sot_cam_cell BL BR ML WL mz1 gnd\n" == line:
                        skip_next = True
                    else:
                        if not skip_next:
                            lines.append(line)
                        skip_next = False
            with open(model_file, 'w') as f:
                for line in lines:
                    f.write(line)
        elif self.is_sotfet:
            current_mirror_mod = os.path.join(OPTS.openram_tech, "sp_lib", "current_mirror.sp")
            self.sf.write(".include {}\n".format(current_mirror_mod))
            # pex mangles box sot_cam_cell pin order, retrieve order from pex and replace in sotfet model
            pex_file = OPTS.pex_spice
            model_instance = ''
            with open(pex_file, 'r') as f:
                previous_line = ''
                for line in f.readlines():
                    if 'sot_cam_cell' in line:
                        model_instance = previous_line + line
                        break
                    previous_line = line
            model_instance = model_instance.replace('\n', '')
            model_instance = model_instance.replace('+', '')
            actual_names = model_instance.split()[1:7]
            orig_names = ["gnd", "ML", "WL", "BL", "BR", "mz1"]
            ordered_pin_names = []
            for actual_name in actual_names:
                for orig_name in orig_names:
                    if orig_name.lower() in actual_name.lower():
                        ordered_pin_names.append(orig_name)
                        continue
            if not len(ordered_pin_names) == 6:  # layout names preserved in extraction
                ordered_pin_names = orig_names
            cam_cell_def = scam_cell_def if OPTS.series else pcam_cell_def
            pins = ' '.join(ordered_pin_names)
            sotfet_params = "ferro_ratio={} reference_vt={} delta_vt={}".format(OPTS.ferro_ratio,
                                                                                OPTS.reference_vt,
                                                                                OPTS.delta_vt)
            self.sf.write(cam_cell_def.format(pins=pins, sotfet_params=sotfet_params))

        self.write_sotfet_includes()

        self.sf.write(".include {}\n".format(OPTS.ic_file))

    def write_sotfet_includes(self):
        cadence_work_dir = os.environ["SYSTEM_CDS_LIB_DIR"]
        p_to_vg = os.path.join(cadence_work_dir, "spintronics/p_to_ids/va_include/p_to_vg.scs")
        sot_cam_cell = os.path.join(cadence_work_dir, "spintronics/sot_llg/spectre/spectre.scs")
        sot_llg = os.path.join(cadence_work_dir, "openram_sot/sot_cam_cell/sim_include/sot_cam_cell.scs")
        ahdl_include = os.path.join(cadence_work_dir, "spintronics/p_to_vg/veriloga/veriloga.va")

        self.sf.write("\nsimulator lang=spectre\n")
        self.sf.write('\ninclude "{0}"\ninclude "{1}"\ninclude "{2}"\nahdl_include "{3}"\n'.format(p_to_vg, sot_llg,
                                                                                                   sot_cam_cell,
                                                                                                   ahdl_include))
        self.sf.write("\nsimulator lang=spice\n")

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

