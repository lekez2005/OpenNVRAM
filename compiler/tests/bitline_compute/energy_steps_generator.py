import os
import shutil

from bl_probe import BlProbe
from globals import OPTS
from sim_steps_generator import SimStepsGenerator


class EnergyStepsGenerator(SimStepsGenerator):

    def write_delay_stimulus(self):
        self.sim_folder = os.path.join(OPTS.openram_temp, OPTS.energy_sim)

        if not os.path.exists(self.sim_folder):
            os.makedirs(self.sim_folder)

        existing_dc = os.path.join(OPTS.openram_temp, "spectre.dc")
        if os.path.exists(existing_dc):
            shutil.copy(existing_dc, self.sim_folder)

        temp_stim = os.path.join(self.sim_folder, "stim.sp")
        self.sf = open(temp_stim, "w")

        self.ic_filename = os.path.join(self.sim_folder, "sram_ic")

        super().write_delay_stimulus()

        # OPTS.tran_options = getattr(OPTS, "tran_options", "") + "readic={}".format(self.ic_filename)

        OPTS.openram_temp = self.sim_folder

    def set_data(self, address, data):
        for col in range(self.sram.num_cols):
            q_label = self.probe.state_probes[address][col]
            self.sf.write("ic {}={} \n".format(q_label, data[self.sram.num_cols-1-col]*0.9))

    def probe_addresses(self, address_data_dict):

        addresses = list(address_data_dict.keys())

        self.stim.replace_pex_subcells()

        self.probe = probe = BlProbe(self.sram, OPTS.pex_spice)

        for address in addresses:
            probe.probe_address(address)

        probe.probe_dout_masks()

        self.run_drc_lvs_pex()

        probe.extract_probes()

        self.sf.write("simulator lang=spectre \n")
        self.sf.write("ic en_0=0 \n")
        self.sf.write("ic en_1=0 \n")

        for address in addresses:
            self.set_data(address, address_data_dict[address])
        self.sf.write("simulator lang=spice \n")

        self.state_probes = probe.state_probes
        self.decoder_probes = probe.decoder_probes
        self.clk_buf_probe = probe.clk_buf_probe
        self.dout_probes = probe.dout_probes
        self.mask_probes = probe.mask_probes

        self.bitline_probes = probe.bitline_probes
        self.br_probes = probe.br_probes

        return probe

    def generate_steps(self):

        if OPTS.baseline:
            self.generate_baseline_energy()
        elif OPTS.serial:
            self.generate_bit_serial_energy()
        else:
            self.generate_bit_parallel_energy()

        self.saved_nodes = list(sorted(list(self.probe.saved_nodes) + list(self.dout_probes.values())
                                       + list(self.mask_probes.values())))

        self.saved_nodes.append(self.clk_buf_probe)


    def generate_bit_serial_energy(self):
        pass

    def generate_bit_parallel_energy(self):
        pass

    def generate_baseline_energy(self):
        if OPTS.energy_sim == "read":
            self.probe_addresses({0: [1, 0]*int(self.sram.num_cols/2)})
            self.baseline_read(0, "Read B ({})".format(0))
            # self.baseline_read(0, "Read B ({})".format(0))
            # self.baseline_read(0, "Read B ({})".format(0))
            # self.baseline_read(0, "Read B ({})".format(0))

