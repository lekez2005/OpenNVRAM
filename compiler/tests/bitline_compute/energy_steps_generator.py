import os
import shutil
import random

from bl_probe import BlProbe
from globals import OPTS
from sim_steps_generator import SimStepsGenerator


class EnergyStepsGenerator(SimStepsGenerator):

    def write_delay_stimulus(self):
        OPTS.num_tries = 10
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

    def initialize(self, address_data_dict):

        addresses = list(address_data_dict.keys())

        self.stim.replace_pex_subcells()

        self.probe = probe = BlProbe(self.sram, OPTS.pex_spice)

        for address in addresses:
            probe.probe_address(address)

        probe.probe_dout_masks()

        self.run_drc_lvs_pex()

        probe.extract_probes()

        self.sf.write("simulator lang=spectre \n")

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

        self.en_0 = self.prev_en_0 = self.en_1 = self.prev_en_1 = 0

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
        func_name = 'test_bs_{}'.format(OPTS.energy_sim)

        if not hasattr(self, func_name):
            return
        else:
            getattr(self, func_name)()

    def generate_bit_parallel_energy(self):
        func_name = 'test_bs_{}'.format(OPTS.energy_sim)

        if not hasattr(self, func_name):
            return
        else:
            getattr(self, func_name)()

    def generate_baseline_energy(self):
        if OPTS.energy_sim == "read":
            self.initialize({0: [1, 0]*int(self.sram.num_cols/2)})
            self.baseline_read(0, "Read B ({})".format(0))
            # self.baseline_read(0, "Read B ({})".format(0))
            # self.baseline_read(0, "Read B ({})".format(0))
            # self.baseline_read(0, "Read B ({})".format(0))

    # Helpers
    def get_random_bin_vector(self, bit_sz):
        MAX_INT = 1 << bit_sz

        _val = random.randint(0, MAX_INT - 1)

        val = []
        for i in range(bit_sz):
            mask   = 1 << i
            digit  = 0 if (_val & mask) == 0 else 1
            val   += [digit]

        return val
 
    def gen_init(self):
        num_rows = self.num_rows
        num_cols = self.num_cols
        word_size = self.word_size

        bit_sz  = num_cols
        MAX_INT = 1 << num_cols

        _init = [random.randint(0, MAX_INT - 1) for i in range(num_rows)]

        init = {}
        for idx in range(num_rows):
            init[idx] = self.get_random_bin_vector(num_cols)

        return init
 
    # Tests
    def test_rd(self):
        num_rows = self.num_rows
        num_cols = self.num_cols
        word_size = self.word_size

        self.initialize(self.gen_init())

        # Read
        for i in range(OPTS.num_tries):
          addr = random.randint(0, num_rows - 1)
          self.rd(addr)

    def test_bs_rd(self): self.test_rd()
    def test_bp_rd(self): self.test_rd()

    def test_wr(self):
        num_rows = self.num_rows
        num_cols = self.num_cols
        word_size = self.word_size

        self.initialize(self.gen_init())

        # Maybe randomize the mask
        mask_all = [1] * num_cols

        for i in range(OPTS.num_tries):
          addr = random.randint(0, num_rows - 1)
          data = self.get_random_bin_vector(num_cols)
          self.wr(addr, data, mask_all)

    def test_bs_wr(self): self.test_wr()
    def test_bp_wr(self): self.test_wr()

    def test_blc(self):
        num_rows = self.num_rows
        num_cols = self.num_cols
        word_size = self.word_size

        self.initialize(self.gen_init())

        for i in range(OPTS.num_tries):
          addr0 = random.randint(0, num_rows - 1)
          addr1 = random.randint(0, num_rows - 1)
          self.blc(addr0, addr1)

    def test_bs_blc(self): self.test_blc()
    def test_bp_blc(self): self.test_blc()

    def test_wb(self):
        num_rows = self.num_rows
        num_cols = self.num_cols
        word_size = self.word_size

        self.initialize(self.gen_init())

        sources = ['and', 'nand', 'nor', 'or', 'xor', 'xnor','data_in']
        for i in range(OPTS.num_tries):
          src = random.choice(sources)
          func_name = 'wb_{}'.format(src)
          getattr(self, func_name)()

    def test_bs_wb(self): self.test_wb()
    def test_bp_wb(self): self.test_wb()

    def test_wb_add(self):
        num_rows = self.num_rows
        num_cols = self.num_cols
        word_size = self.word_size

        self.initialize(self.gen_init())

        for i in range(OPTS.num_tries):
          func_name = 'wb_{}'.format('add')
          getattr(self, func_name)()

    def test_bs_wb_add(self): self.test_wb_add()
    def test_bp_wb_add(self): self.test_wb_add()

    def test_wb_mask(self):
        num_rows = self.num_rows
        num_cols = self.num_cols
        word_size = self.word_size

        self.initialize(self.gen_init())

        # Get random source
        sources = ['and', 'nand', 'nor', 'or', 'xor', 'xnor','data_in']
        for i in range(OPTS.num_tries):
          src = random.choice(sources)
          func_name = 'wb_mask_{}'.format(src)
          getattr(self, func_name)()

    def test_bs_wb_mask(self): self.test_wb_mask()
    def test_bp_wb_mask(self): self.test_wb_mask()

    def test_wb_mask_add(self):
        num_rows = self.num_rows
        num_cols = self.num_cols
        word_size = self.word_size

        self.initialize(self.gen_init())

        for i in range(OPTS.num_tries):
          func_name = 'wb_mask_{}'.format('add')
          getattr(self, func_name)()

    def test_bs_wb_mask_add(self): self.test_wb_mask_add()
    def test_bp_wb_mask_add(self): self.test_wb_mask_add()
