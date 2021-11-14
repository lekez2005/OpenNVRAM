from characterizer.stimuli import stimuli
from globals import OPTS
from modules.mram.spice_dut import SpiceDut


class SotfetCamDut(SpiceDut):
    def instantiate_sram(self, sram):
        stimuli.instantiate_sram(self, sram)
        self.one_t_one_s = getattr(OPTS, "one_t_one_s", False)
        self.gen_constant("search_ref", OPTS.sense_amp_vref, gnd_node="gnd")

    @staticmethod
    def replace_sotfet_cells(definition_split, match_groups, replacement_f, format_tx):
        tx_num = match_groups["tx_num"]
        if tx_num[0] in ["3", "3@2"]:
            replacement_f.write(format_tx())
        else:
            drain, gate, source, body = definition_split[1:5]
            name_template = OPTS.bitcell_name_template
            terminals = definition_split[1:5]

            bitline_prefix = f"N_Xbank{match_groups['bank']}_b"
            bitline_net = [x for x in terminals if x.startswith(bitline_prefix)][0]

            if tx_num == "0":
                sot_gate_template = OPTS.sot_1_template
                instance_name = "XI0"
            else:
                sot_gate_template = OPTS.sot_2_template
                instance_name = "XI1"
            sot_gate = sot_gate_template.format(**match_groups)

            if OPTS.sotfet_cam_mode == "pcam":
                ml_net = [x for x in terminals if "ml[" in x][0]
                adjacent_index = 2 if terminals.index(ml_net) == 0 else 0
                adjacent_net = terminals[adjacent_index]
                source_net, drain_net = adjacent_net, ml_net
                gate_plus, gate_minus = sot_gate, bitline_net
            else:
                vmid_net = [x for x in terminals if "vmid" in x][0]

                adjacent_index = 2 if terminals.index(vmid_net) == 0 else 0
                adjacent_net = terminals[adjacent_index]
                source_net, drain_net = vmid_net, adjacent_net
                gate_plus, gate_minus = bitline_net, sot_gate

            sot_cell_name = "{}_{}".format(name_template.format(**match_groups), instance_name)
            sotfet_definition = f"{sot_cell_name} {drain_net} {gate_plus} {gate_minus} {source_net} {body} sotfet\n"

            replacement_f.write(sotfet_definition)
