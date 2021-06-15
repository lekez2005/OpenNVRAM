import re

import debug
from globals import OPTS
from shared_decoder.shared_probe import SharedProbe


class MramProbe(SharedProbe):

    def __init__(self, sram, pex_file=None):
        super().__init__(sram, pex_file)
        self.wwl_probes = self.voltage_probes["wwl"] = {}

    def get_bank_bitcell_current_probes(self, bank, bits, row, col_index):
        if OPTS.use_pex:
            template = "Xsram.Xbank{}_Xbitcell_array_Xbit_r{}_c{}_XI0.VIY"
        else:
            template = "Xsram.Xbank{}.Xbitcell_array.Xbit_r{}_c{}.XI0.VIY"
        results = []
        for bit in bits:
            col = col_index + bit * self.sram.words_per_row
            results.append((bit, template.format(bank, row, col)))
        return results

    def get_control_buffers_probe_bits(self, destination_inst, bank):
        name = destination_inst.name
        if name in ["wwl_driver", "rwl_driver"]:
            return [self.sram.bank.num_rows - 1]
        else:
            return super().get_control_buffers_probe_bits(destination_inst, bank)

    def sense_amp_current_probes(self, bank, bits):
        if OPTS.mram == "sot":
            nets = ["sense_out_bar"]
        else:
            nets = ["sense_out", "sense_out_bar"]
        probes = self.bitline_current_probes(bank, bits, modules=["sense_amp_array"],
                                             nets=nets, suffix="")
        self.update_current_probes(probes, "sense_amp_array", bank)

    def get_sense_amp_internal_nets(self):
        child_mod = self.sram.bank.sense_amp_array.child_mod
        probes = ["dout", "dout_bar", "bl", "vref"]
        if OPTS.mram == "sot":
            probes.extend(["vdata"])
        return self.filter_internal_nets(child_mod, probes)

    def get_wordline_nets(self):
        return ["wwl", "rwl"]

    def get_bitcell_label(self, bank_index, row, col, pin_name):
        if OPTS.use_pex:
            return self.get_storage_node_pattern().format(bank=bank_index, row=row,
                                                          col=col, name="Xbit")
        else:
            return super().get_bitcell_label(bank_index, row, col,
                                             pin_name=OPTS.bitcell_state_probe)

    def get_storage_node_pattern(self):
        if OPTS.use_pex:
            pattern = "Xsram.{}_{}".format(OPTS.bitcell_name_template,
                                           OPTS.bitcell_state_probe)
        else:
            pattern = super().get_storage_node_pattern()
        debug.info(2, "Storage node pattern = {}".format(pattern))
        return pattern

    def extract_state_probes(self, existing_mappings):
        if OPTS.use_pex:
            for address_vals in self.state_probes.values():
                self.saved_nodes.update(address_vals)
        else:
            for key in self.state_probes:
                self.extract_nested_probe(key, self.state_probes, existing_mappings)

        if not OPTS.mram == "sot":
            return
        # add ref probes
        pattern = self.get_storage_node_pattern()
        for key in self.state_probes:
            address_int = int(key)
            bank_index, bank_inst, row, col_index = self.decode_address(address_int)
            for i in range(0, OPTS.num_reference_cells, 2):
                for ref_offset in range(2):
                    col = i * 2 + ref_offset
                    state_probe = pattern.format(bank=bank_index, row=row, col=col,
                                                 name="Xref")
                    self.saved_nodes.add(state_probe)

    def get_wordline_label(self, bank_index, row, col):
        return self.get_w_label(bank_index, row, col).replace("wl", "rwl")

    def get_wwl_label(self, bank_index, row, col):
        return self.get_w_label(bank_index, row, col).replace("wl", "wwl")

    def probe_address(self, address, pin_name="q"):
        super().probe_address(address, pin_name)

        address = self.address_to_vector(address)
        address_int = self.address_to_int(address)
        bank_index, bank_inst, row, col_index = self.decode_address(address)

        # add wwl probe
        col = self.sram.num_cols - 1
        self.wwl_probes[address_int] = self.get_wwl_label(bank_index, row, col)

        if self.two_bank_dependent:
            self.probe_labels.add(self.wwl_probes[address_int])
            self.wwl_probes[address_int] = self.get_wwl_label(1, row, col)

        self.probe_labels.add(self.wwl_probes[address_int])
