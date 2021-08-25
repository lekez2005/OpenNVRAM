import numpy as np

import debug
from characterizer.dependency_graph import get_instance_module
from characterizer.net_probes.sram_probe import SramProbe
from globals import OPTS


class CamProbe(SramProbe):

    def __init__(self, sram, pex_file=None):
        super().__init__(sram, pex_file)
        self.ml_probes = self.voltage_probes["ml"] = {}

    def probe_bank(self, bank):
        super().probe_bank(bank)
        self.probe_matchlines(bank)
        self.probe_dout(bank)

    def probe_control_flops(self, bank):
        self.probe_labels.add("Xsram.Xbank{}.search_buf".format(bank))
        self.probe_labels.add("Xsram.Xbank{}.bank_sel_buf".format(bank))

    def get_delay_probe_rows(self):
        if OPTS.verbose_save:
            return list(range(self.sram.bank.num_rows))
        return [int(x) for x in np.linspace(0, self.sram.bank.num_rows - 1, 5)]

    def sense_amp_current_probes(self, bank, bits):
        pass

    def probe_sense_amps(self, bank):
        pass

    def tri_state_current_probes(self, bank, bits):
        pass

    def get_control_buffers_probe_bits(self, destination_inst, bank):
        name = destination_inst.name
        if name == "search_sense_amps":
            return list(range(self.sram.bank.num_rows))
        return super().get_control_buffers_probe_bits(destination_inst, bank)

    def precharge_current_probes(self, bank, cols):
        probes = self.bitline_current_probes(bank, cols, modules=["precharge_array"],
                                             suffix="")
        self.update_current_probes(probes, "precharge_array", bank)

        # TODO matchline currents

    def get_bitcell_current_nets(self):
        return ["ml"]

    def get_search_sense_amp_internal_nets(self):
        nets = ["dout", "vin"]
        debug.info(2, "search sense amp internal nets: %s", ", ".join(nets))
        return nets

    def probe_matchlines(self, bank):
        sample_net = "ml[0]"
        bank_name = 'bank{}'.format(bank)
        bank_inst = get_instance_module(bank_name, self.sram)
        search_sense_inst = bank_inst.mod.search_sense_inst

        self.probe_internal_nets(bank, sample_net=sample_net, array_inst=search_sense_inst,
                                 internal_nets=self.get_search_sense_amp_internal_nets())
        self.ml_probes[bank] = self.voltage_probes[search_sense_inst.name][bank]["vin"]

    def probe_dout(self, bank):
        if len(self.dout_probes) > self.sram.num_banks:
            self.dout_probes.clear()
        probes = self.dout_probes[bank] = {}
        if bank > 0:
            suffix = f"_{bank}"
        else:
            suffix = ""
        for row in range(self.sram.bank.num_rows):
            probes[row] = f"search_out[{row}]{suffix}"
