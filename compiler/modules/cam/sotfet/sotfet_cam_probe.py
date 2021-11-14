import debug
from modules.cam.cam_probe import CamProbe
from globals import OPTS


class SotfetCamProbe(CamProbe):
    def extract_state_probes(self, existing_mappings):
        if OPTS.use_pex:
            for address_vals in self.state_probes.values():
                self.saved_nodes.update(address_vals)
        else:
            for key in self.state_probes:
                self.extract_nested_probe(key, self.state_probes, existing_mappings)

    def get_bitcell_label(self, bank_index, row, col, pin_name):
        if OPTS.use_pex:
            return self.get_storage_node_pattern().format(bank=bank_index, row=row,
                                                          col=col, name="Xbit")
        else:
            return super().get_bitcell_label(bank_index, row, col,
                                             pin_name=OPTS.bitcell_state_probe)

    def update_bitcell_labels(self, pin_labels):
        if not OPTS.use_pex:
            self.probe_labels.update(pin_labels)

    def get_storage_node_pattern(self):
        if OPTS.use_pex:
            pattern = "Xsram.{}_{}".format(OPTS.bitcell_name_template,
                                           OPTS.bitcell_state_probe)
        else:
            pattern = super().get_storage_node_pattern()
        debug.info(2, "Storage node pattern = {}".format(pattern))
        return pattern

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

    def get_search_sense_amp_internal_nets(self):
        # nets = ["dout", "vin_int", "vcomp_int", "vin"]
        nets = ["dout", "vin"]
        debug.info(2, "search sense amp internal nets: %s", ", ".join(nets))
        return nets
