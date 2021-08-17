import os
import re

import debug
from base.utils import load_module
from characterizer.stimuli import stimuli
from globals import OPTS
from modules.baseline_sram import BaselineSram


class SpiceDut(stimuli):
    """
    Instantiates the sram
    External peripheral spice should also be instantiated here
    """

    def instantiate_sram(self, sram: BaselineSram):
        abits = sram.addr_size
        dbits = sram.word_size
        num_banks = sram.num_banks if OPTS.independent_banks else 1
        sram_name = sram.name

        self.sf.write("Xsram ")

        for j in range(num_banks):
            for i in range(dbits):
                self.sf.write("D[{0}] ".format(i))
                self.sf.write("mask[{0}] ".format(i))
        if OPTS.independent_banks and num_banks == 2:
            abits -= 1
        for i in range(abits):
            self.sf.write("A[{0}] ".format(i))

        control_pins = sram.bank.connections_from_mod(sram.control_pin_names,
                                                      [("ADDR[", "A[")])
        self.sf.write(" {0} {1} {2} ".format(" ".join(control_pins),
                                             self.vdd_name, self.gnd_name))

        self.one_t_one_s = getattr(OPTS, "one_t_one_s", False)

        if OPTS.mram == "sotfet":
            self.sf.write(" vref ")
        elif OPTS.mram == "sot":
            self.sf.write(" vclamp ")
        if self.one_t_one_s:
            self.sf.write("rw")

        self.sf.write(" {0}\n".format(sram_name))

        if OPTS.mram == "sotfet":
            self.gen_constant("vref", OPTS.sense_amp_vref, gnd_node="gnd")
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
        params["tech_name"] = OPTS.tech_name

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
        debug.info(1, "Replacing bitcells in pex file")
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

        split = tx_definition.split()
        tx_name = split[0]  # type: str
        parameters = split[5:]

        def format_tx():
            drain, gate, source, body = split[1:5]
            tx_terminals = "\n+ ".join([tx_name, drain, gate, source, body])
            return tx_terminals + "\n+ " + " ".join(parameters) + "\n"

        regex_pattern = re.compile(OPTS.pex_replacement_pattern)

        match_groups = regex_pattern.search(tx_name).groupdict()

        args = [split, match_groups, replacement_f, format_tx]
        if OPTS.mram == "sot":
            self.replace_sot_cells(*args)
        elif self.one_t_one_s:
            self.replace_1t1s_cells(*args)
        elif OPTS.mram == "sotfet":
            self.replace_sotfet_cells(*args)

    @staticmethod
    def replace_sot_cells(definition_split, match_groups, replacement_f, format_tx):

        drain, gate, source, body = definition_split[1:5]

        name_template = OPTS.bitcell_name_template
        tx_num = match_groups["tx_num"]

        if tx_num[0] == "0":
            replacement_f.write(format_tx())
        else:
            sot_p = (name_template + "_sot_p").format(**match_groups)
            mtj_top = (name_template + "_mtj_top").format(**match_groups)
            assert "br[" in source, "Sanity check to confirm br[ is connected to source"
            br_net = source
            definition_split[3] = mtj_top  # source
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

    @staticmethod
    def replace_sotfet_cells(definition_split, match_groups, replacement_f, format_tx):
        tx_num = match_groups["tx_num"]
        if tx_num[0] in ["0", "2"]:
            replacement_f.write(format_tx())
        else:
            drain, gate, source, body = definition_split[1:5]
            name_template = OPTS.bitcell_name_template
            sf_drain = (name_template + "_sf_drain").format(**match_groups)
            sot_p = (name_template + "_sot_p").format(**match_groups)
            br_net = source
            sot_cell_name = "{}_XI0".format(name_template.format(**match_groups))
            assert sf_drain == drain, "Sanity check to confirm sf_drain"
            assert "virtual_gate" in gate, "Sanity check to confirm virtual_gate"
            assert "br[" in source.lower(), "Sanity check to confirm br[ is connected to source"
            replacement_f.write("{} {} {} {} {} {} {}\n".format(sot_cell_name, sf_drain, sot_p,
                                                                br_net, br_net, body, "sotfet"))

    @staticmethod
    def replace_1t1s_cells(definition_split, match_groups, replacement_f, format_tx):
        tx_num = match_groups["tx_num"]
        if tx_num[0] == "0":
            replacement_f.write(format_tx())
        else:
            drain, gate, source, body = definition_split[1:5]
            name_template = OPTS.bitcell_name_template
            sot_p = (name_template + "_sot_p").format(**match_groups)
            bl_net = drain
            rwl_net = source
            sotfet_cell_name = "{}_XI0".format(name_template.format(**match_groups))
            assert "bl[" in bl_net, "Sanity check to confirm bl_net"
            assert "sot_p" in sot_p, "Sanity check to confirm sot_p"
            assert "rwl[" in source.lower(), "Sanity check to confirm rwl[ is connected to source"
            replacement_f.write("{} {} {} {} {} {} {}\n".format(sotfet_cell_name, bl_net, bl_net,
                                                                sot_p, rwl_net, body, "sotfet"))
