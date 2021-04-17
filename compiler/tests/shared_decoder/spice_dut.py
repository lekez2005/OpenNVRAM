import os
import re

from base.utils import load_module
from characterizer.stimuli import stimuli
from globals import OPTS
from modules.shared_decoder.cmos_sram import CmosSram


class SpiceDut(stimuli):
    """
    Instantiates the sram
    External peripheral spice should also be instantiated here
    """

    def instantiate_sram(self, sram: CmosSram):
        abits = sram.addr_size
        dbits = sram.word_size
        num_banks = sram.num_banks
        sram_name = sram.name

        self.sf.write("Xsram ")

        for j in range(num_banks):
            for i in range(dbits):
                self.sf.write("D[{0}] ".format(i))
                self.sf.write("mask[{0}] ".format(i))
        actual_a_bits = abits if num_banks == 1 else abits - 1
        for i in range(actual_a_bits):
            self.sf.write("A[{0}] ".format(i))

        self.sf.write(" {0} {1} {2} ".format(" ".join(sram.control_pin_names),
                                             self.vdd_name, self.gnd_name))

        if OPTS.mram == "sotfet":
            self.sf.write(" vref ")
        elif OPTS.mram == "sot":
            self.sf.write(" vclamp ")

        self.sf.write(" {0}\n".format(sram_name))

        if OPTS.mram == "sotfet":
            self.gen_constant("vref", OPTS.sense_amp_ref, gnd_node="gnd")
        elif OPTS.mram == "sot":
            self.gen_constant("vclamp", OPTS.sense_amp_vclamp, gnd_node="gnd")

    def write_include(self, circuit):
        super().write_include(circuit)

        if OPTS.mram:
            self.add_device_model()

    def add_device_model(self):

        if not OPTS.use_pex:
            lvs_model = OPTS.mram_bitcell.split("/")[-1]
            sim_sp_file = os.path.join(OPTS.openram_temp, "sram.sp")
            self.remove_subckt(lvs_model, sim_sp_file)
            if OPTS.mram == "sot":
                self.remove_subckt(OPTS.ref_bitcell.split("/")[-1], sim_sp_file)

            schematic_model = os.path.join(OPTS.openram_tech, "sp_lib",
                                           OPTS.schematic_model_file)
            self.sf.write(".include \"{0}\"\n".format(schematic_model))

        # update device parameters
        params_path = os.path.join(OPTS.openram_tech, "sp_lib", OPTS.default_model_params)
        default_params = load_module(params_path)
        params = {key: getattr(default_params, key) for key in dir(default_params)
                  if not key.startswith("__")}
        for key in dir(OPTS):
            if key in params:
                params[key] = getattr(OPTS, key)

        def include_model(source_file):
            model_path = os.path.join(OPTS.openram_tech, "sp_lib", source_file)
            destination_file = os.path.join(OPTS.openram_temp, os.path.basename(model_path))
            with open(model_path, "r") as model_file, \
                    open(destination_file, "w") as destination:
                model_content = model_file.read()
                model_content = model_content.format(**params)
                destination.write(model_content)
            self.sf.write(".include \"{0}\"\n".format(destination_file))

        include_model(OPTS.model_file)
        if OPTS.mram == "sot":
            include_model(OPTS.ref_model_file)

    def replace_bitcell(self, delay_obj):
        if not OPTS.use_pex or not getattr(OPTS, "mram", False):
            return
        # derive replacement file
        pex_file = delay_obj.trim_sp_file
        basename = os.path.splitext(os.path.basename(pex_file))[0]
        replacement = os.path.join(os.path.dirname(pex_file), basename + ".mod.sp")

        delay_obj.trim_sp_file = replacement

        if (os.path.exists(replacement) and
                os.path.getmtime(replacement) > os.path.getmtime(pex_file) and False):
            return

        replacement_tx_pattern = OPTS.pex_replacement_pattern
        regex_pattern = re.compile(replacement_tx_pattern, re.IGNORECASE)

        with open(pex_file, "r") as pex_f, open(replacement, "w") as replacement_f:
            within_tx_definition = False
            tx_definition = ""
            for line in pex_f:
                if not line:
                    replacement_f.write(line)
                elif within_tx_definition:
                    if not line[0] == "+":
                        within_tx_definition = False
                        self.process_tx_definition(tx_definition, replacement_f)
                        if line[0] == replacement_tx_pattern[0] and regex_pattern.search(line):
                            within_tx_definition = True
                            tx_definition = line.strip()
                        else:
                            replacement_f.write(line)
                    else:
                        tx_definition += " " + line[1:].strip()
                else:
                    if line[0] == replacement_tx_pattern[0] and regex_pattern.search(line):
                        within_tx_definition = True
                        tx_definition = line.strip()
                    else:
                        replacement_f.write(line)

    def process_tx_definition(self, tx_definition, replacement_f):
        if OPTS.mram == "sot":
            self.replace_sot_cells(tx_definition, replacement_f)

    def replace_sot_cells(self, tx_definition, replacement_f):
        split = tx_definition.split()
        tx_name = split[0]  # type: str
        drain, gate, source, body = split[1:5]
        parameters = split[5:]

        def format_tx():
            tx_terminals = "\n+ ".join([tx_name, drain, gate, source, body])
            return tx_terminals + "\n+ " + " ".join(parameters) + "\n"

        regex_pattern = re.compile(OPTS.pex_replacement_pattern)

        match_groups = regex_pattern.search(tx_name).groupdict()
        tx_num = match_groups["tx_num"]

        name_template = OPTS.bitcell_name_template

        if tx_num[0] == "0":
            replacement_f.write(format_tx())
        else:
            sot_p = (name_template + "_sot_p").format(**match_groups)
            mtj_top = (name_template + "_mtj_top").format(**match_groups)
            assert "br[" in source, "Sanity check to confirm br[ is connected to source"
            br_net = source
            source = mtj_top
            replacement_f.write(format_tx())
            sot_cell_name = "{}_XI0".format(name_template.format(**match_groups))
            # only sot model add to first finger
            if "@" not in tx_num:
                # reverse pin of mtj ref odd index
                col = int(match_groups["col"])
                if match_groups["name"] == "Xref" and col % 2 == 1:
                    model_name = "sot_cell_ref"
                else:
                    model_name = "sot_cell"
                replacement_f.write("{} {} {} {} {}\n".
                                    format(sot_cell_name,
                                           mtj_top, br_net, sot_p, model_name))

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
