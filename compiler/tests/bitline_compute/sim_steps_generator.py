import os
import random
from importlib import reload
from math import ceil

import characterizer
import verify
from bl_probe import BlProbe
from characterizer.sequential_delay import SequentialDelay
from globals import OPTS
from spice_dut import SpiceDut


class SimStepsGenerator(SequentialDelay):

    ramp_time = period = 0
    write_period = read_period = 0
    read_duty_cycle = write_duty_cycle = 0.5
    saved_nodes = []
    saved_currents = []
    first_output = True

    def __init__(self, sram, spfile, corner, initialize=False):
        super().__init__(sram, spfile, corner, initialize=initialize)

        for i in range(self.word_size):
            self.bus_sigs.append("mask[{}]".format(i))
        if OPTS.baseline:
            self.control_sigs = ["read", "acc_en", "acc_en_inv", "sense_trig", "bank_sel"]
            self.select_sigs = []
            self.words_per_row = self.sram.words_per_row
        else:
            if OPTS.serial:
                self.words_per_row = self.sram.num_cols
            else:
                self.words_per_row = self.sram.alu_num_words

            for i in range(self.addr_size):
                self.bus_sigs.append("A_1[{}]".format(i))

            self.bus_selects = ["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor", "s_sum", "s_data"]

            if OPTS.serial:
                self.bus_selects = ["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor",
                                    "s_sum", "s_data", "s_cout"]
                self.sr_in_selects = ["s_bus", "s_mask_in"]
                self.sr_out_selects = ["s_sr", "s_lsb", "s_msb"]
                self.select_sigs = self.bus_selects + self.sr_in_selects
                self.control_sigs = ["read", "en_0", "en_1", "acc_en", "acc_en_inv", "bank_sel", "sense_trig",
                                     "diff", "diffb", "sr_en", "mask_en"] + self.select_sigs
            else:
                self.sr_in_selects = ["s_bus", "s_mask_in", "s_shift"]
                self.sr_out_selects = ["s_sr", "s_lsb", "s_msb"]
                self.bus_selects = ["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor", "s_sum", "s_data"]

                self.select_sigs = self.bus_selects + self.sr_in_selects + self.sr_out_selects
                self.control_sigs = (["read", "en_0", "en_1", "acc_en", "acc_en_inv", "bank_sel", "sr_en",
                                      "diff", "diffb", "sense_trig"] + self.select_sigs)

            for i in range(self.words_per_row):
                if OPTS.serial:
                    self.bus_sigs.append("c_val[{}]".format(i))
                else:
                    self.bus_sigs.append("cin[{}]".format(i))

        for sig in self.select_sigs:
            setattr(self, sig, 0)
            setattr(self, "prev_"+sig, 0)

        # set up for write
        self.diff = self.prev_diff = 1
        self.diffb = self.prev_diffb = 0

        self.sense_trig = self.prev_sense_trig = 0
        self.bank_sel = self.prev_bank_sel = 1
        self.sr_en = self.prev_sr_en = 1
        self.read = self.prev_read = 1
        self.en_0 = self.prev_en_0 = 0
        self.en_1 = self.prev_en_1 = 0
        self.mask = self.prev_mask = [1] * OPTS.word_size
        self.cin = self.prev_cin = [1]*self.words_per_row
        if OPTS.serial:
            self.c_val = self.prev_c_val = [1]*self.words_per_row
            self.mask_en = self.prev_mask_en = 1
        mid_address = int(0.5 * self.sram.num_words)
        self.address_1 = self.prev_address_1 = self.convert_address(mid_address)

        self.inverted_sels = ["s_sr"]

    def write_pwl(self, key, prev_val, curr_val):
        """Append current time's data to pwl. Transitions from the previous value to the new value using the slew"""

        if prev_val == curr_val and self.current_time > 1.5*self.period:
            return

        if key in ["clk", "bank_sel"]:
            setup_time = 0
        elif key in ["acc_en", "acc_en_inv"]: # to prevent contention with tri-state buffer
            setup_time = -0.5*self.duty_cycle*self.period
        elif self.current_time > self.period and hasattr(self, "sr_in_selects") and key in self.sr_in_selects:
            setup_time = (1-self.duty_cycle)*self.period
        elif key == "sense_trig":
            if prev_val == 0:
                setup_time = -(self.duty_cycle*self.period + OPTS.sense_trigger_delay)
            else:
                setup_time = -(self.slew + 0.03)  # temporary hard-code to minimize glitch
        elif (key == "diff" and prev_val == 1) or (key == "diffb" and prev_val == 0):
            setup_time = ((1-self.duty_cycle) * self.period) + OPTS.diff_setup_time
        else:
            setup_time = self.setup_time

        if key in self.inverted_sels:
            prev_val, curr_val = int(not prev_val), int(not curr_val)

        t1 = max(0.0, self.current_time - 0.5 * self.slew - setup_time)
        t2 = max(0.0, self.current_time + 0.5 * self.slew - setup_time)
        self.v_data[key] += " {0}n {1}v {2}n {3}v ".format(t1, self.vdd_voltage * prev_val, t2,
                                                           self.vdd_voltage * curr_val)
        self.v_comments[key] += " ({0}, {1}) ".format(int(self.current_time / self.period),
                                                      curr_val)

    def write_delay_stimulus(self):
        """ Override super class method to use internal logic for pwl voltages and measurement setup
         Creates a stimulus file for simulations to probe a bitcell at a given clock period.
        """
        self.duty_cycle = self.read_duty_cycle
        self.period = self.read_period

        reload(characterizer)

        # creates and opens stimulus file for writing
        self.current_time = 0
        if not getattr(self, "sf", None):
            temp_stim = os.path.join(OPTS.openram_temp, "stim.sp")
            self.sf = open(temp_stim, "w")
        self.sf.write("{} \n".format(self.sram))
        if OPTS.spice_name == "spectre":
            self.sf.write("simulator lang=spice\n")
        self.sf.write("* Delay stimulus for read period = {0}n, write period = {1}n "
                      " read duty = {2}n write duty = {3}n Area={4:.0f}um2 load={5}fF slew={6}n\n\n".format(
            self.read_period, self.write_period, self.read_duty_cycle, self.write_duty_cycle,
            (self.sram.width*self.sram.height),
            self.load, self.slew))

        self.stim = SpiceDut(self.sf, self.corner)
        self.stim.words_per_row = self.words_per_row

        self.write_generic_stimulus()

        if not OPTS.baseline:
            self.stim.gen_constant("sense_amp_ref", OPTS.sense_amp_ref, gnd_node="gnd")

        self.initialize_output()

        self.generate_steps()

        for node in self.saved_nodes:
            self.sf.write(".probe V({0}) \n".format(node))

        self.sf.write("simulator lang=spectre \n")
        for node in self.saved_currents:
            self.sf.write("save {0} \n".format(node))
        self.sf.write("simulator lang=spice \n")

        self.finalize_output()

        self.stim.write_include(self.trim_sp_file)

        # run until the end of the cycle time
        self.stim.write_control(self.current_time + self.period)

        self.sf.close()

    def probe_addresses(self, addresses):

        self.stim.replace_pex_subcells()

        probe = BlProbe(self.sram, OPTS.pex_spice)

        probe.probe_bitlines(0)
        probe.probe_misc_bank(0)
        probe.probe_write_drivers()
        probe.probe_dout_masks()
        probe.probe_latched_sense_amps()
        if not OPTS.baseline:
            probe.probe_alu()
        probe.probe_currents(addresses)

        for address in addresses:
            probe.probe_address(address)
        probe.bitcell_probes = probe.state_probes

        self.run_drc_lvs_pex()

        probe.extract_probes()

        self.state_probes = probe.state_probes
        self.decoder_probes = probe.decoder_probes
        self.clk_buf_probe = probe.clk_buf_probe
        self.dout_probes = probe.dout_probes
        self.mask_probes = probe.mask_probes

        self.bitline_probes = probe.bitline_probes
        self.br_probes = probe.br_probes

        return probe

    def generate_steps(self):
        # TODO addresses to use?
        a_address = self.sram.num_words - 1  # measure using topmost row
        b_address = 0
        c_address = int(self.sram.num_words/2)

        num_cols = self.num_cols
        word_size = self.word_size

        def select_cols(x):
            if len(x) >= num_cols:
                return x[:num_cols]
            else:
                repeats = ceil(num_cols/len(x))
                return (x*repeats)[:num_cols]

        data_one = select_cols([0]*word_size + [1, 0, 0, 1]*int(word_size/4))
        data_two = select_cols([0]*(word_size-1) + [1] + [1, 0, 1, 0]*int(word_size/4))
        data_three = select_cols([1] * word_size + [1, 1, 0, 0] * int(word_size / 4))

        mask_one = select_cols([1]*(2*word_size))
        mask_two = select_cols([1] * (2 * word_size))
        mask_three = select_cols([1]*word_size + [1, 1, 0, 0]*int(word_size/4))

        a_data = [data_three[i] if mask_three[i] else data_one[i] for i in range(num_cols)]
        b_data = data_two

        probe = self.probe_addresses([a_address, b_address, c_address])

        self.command_comments.append("* Period = {} \n".format(self.period))
        self.command_comments.append("* Duty Cycle = {} \n".format(self.duty_cycle))

        self.test_blc()
        quick_read = False
        if OPTS.baseline:
            self.baseline_write(a_address, data_one, mask_one, "Write A ({})".format(a_address))

            self.setup_write_measurements(b_address)
            self.baseline_write(b_address, data_two, mask_two, "Write B ({})".format(b_address))

            self.setup_read_measurements(b_address)
            self.baseline_read(b_address, "Read B ({})".format(b_address))

            self.setup_write_measurements(c_address)
            self.baseline_write(c_address, data_three, mask_three, "Write C ({})".format(c_address))

            self.setup_read_measurements(a_address)
            self.baseline_read(a_address, "Read A ({})".format(a_address))

            self.setup_read_measurements(b_address)
            self.baseline_read(b_address, "Read B ({})".format(b_address))

            self.setup_write_measurements(a_address)
            self.baseline_write(a_address, data_three, mask_three, "Write A ({})".format(a_address))
        elif quick_read:
            self.bank_sel = 1
            self.acc_en = self.read = 1
            self.acc_en_inv = 0
            existing_data = {
                a_address: [0, 0, 1, 1] * int(num_cols / 4),
                b_address: [0, 1, 0, 1] * int(num_cols / 4)
            }
            self.initialize_sram(probe, existing_data)
            self.setup_read_measurements(b_address)
            self.bitline_compute(a_address, b_address, bus_sel="s_nor", sr_in="s_mask_in",
                                 sr_out="s_sr", comment=" A + B")
            self.setup_write_measurements(a_address)
            self.write_masked_data(b_address, data_two, mask_two, "Write B ({})".format(b_address))
        else:
            self.bank_sel = 1
            self.acc_en = self.read = 0
            self.acc_en_inv = 1

            self.write_masked_data(a_address, data_one, mask_one, "Write A ({})".format(a_address))

            self.setup_write_measurements(b_address)
            self.write_masked_data(b_address, data_two, mask_two, "Write B ({})".format(b_address))

            self.setup_write_measurements(a_address)
            self.write_masked_data(a_address, data_three, mask_three, "Write A ({})".format(a_address))

            self.setup_read_measurements(b_address)
            self.read_data(b_address, "Read B ({})".format(b_address))

            # Read A effectively sum =  A + 0
            self.cin = [0]*self.words_per_row
            self.setup_read_measurements(a_address)
            self.read_data(a_address, "Read A ({})".format(a_address))

            # BL compute C = A + B
            self.cin = [0, 1]*max(1, int(self.words_per_row/2))
            self.setup_read_measurements(a_address)
            self.bitline_compute(a_address, b_address, bus_sel="s_sum", sr_in="s_mask_in",
                                 sr_out="s_sr", comment=" A + B")

            self.sr_en = 0
            self.setup_write_measurements(c_address)
            self.write_back(c_address, bus_sel="s_sum", sr_in="s_mask_in", sr_out="s_sr",
                            comment="Write-back MASK-IN to C ({})".format(c_address))

            self.sr_en = 1

            # ---- Multiplication -----
            # Read A
            self.setup_read_measurements(a_address)
            # Read A bar into SR to ensure there will be transition when A is later read into it
            mask_in = [int(not x) for x in a_data]
            self.mask = list(reversed(mask_in))
            self.set_selects(sr_in="s_mask_in")
            self.read_data(a_address, comment="Read A ({})".format(a_address))

            # SR = A ( from previous read ), here measure msb to mask_in_bar transition time
            self.write_shift_register(bus_sel="s_and", sr_in="s_bus", sr_out="s_msb", comment="Shift-Register")

            if not OPTS.serial:
                # Write back B + C if MSB
                self.setup_read_measurements(b_address)
                self.sr_en = 0
                self.bitline_compute(b_address, c_address, bus_sel="s_sum", sr_in="s_shift",
                                     sr_out="s_sr", comment=" B + C ")
                self.sr_en = 0
                self.setup_write_measurements(c_address)
                self.write_back(c_address, bus_sel="s_sum", sr_in="s_shift", sr_out="s_msb",
                                comment="Write-back MSB mask to C ({})".format(c_address))
                # Write back B + C if MSB
                self.setup_read_measurements(b_address)
                self.bitline_compute(b_address, c_address, bus_sel="s_sum", sr_in="s_bus",
                                     sr_out="s_sr", comment=" B + C")
                self.sr_en = 1  # shift once, here measure lsb to mask_in_bar transition
                self.setup_write_measurements(c_address)
                self.write_back(c_address, bus_sel="s_sum", sr_in="s_shift", sr_out="s_lsb",
                                comment="Write-back LSB mask to C ({})".format(c_address))

        self.saved_nodes = list(sorted(list(probe.saved_nodes) + list(self.dout_probes.values())
                                       + list(self.mask_probes.values())))

        self.saved_nodes.append(self.clk_buf_probe)

        self.saved_currents = probe.current_probes

    @staticmethod
    def invert_vec(data_vec):
        return [0 if x == 1 else 1 for x in data_vec]

    @staticmethod
    def probe_matchlines(probe, cam):
        for i in range(cam.num_words):
            probe.probe_matchline(i)

    def update_output(self, increment_time=True):
        # write address1
        if not OPTS.baseline:
            for i in range(self.addr_size):
                key = "A_1[{}]".format(i)
                self.write_pwl(key, self.prev_address_1[i], self.address_1[i])
            self.prev_address_1 = self.address_1
        # write cin
        if not OPTS.baseline:
            if OPTS.serial:
                for i in range(self.num_cols):
                    key = "c_val[{}]".format(i)
                    self.write_pwl(key, self.prev_c_val[i], self.c_val[i])
                self.prev_c_val = self.c_val
            else:
                for i in range(self.words_per_row):
                    key = "cin[{}]".format(i)
                    self.write_pwl(key, self.prev_cin[i], self.cin[i])
                self.prev_cin = self.cin
        # write mask
        for i in range(self.word_size):
            key = "mask[{}]".format(i)
            self.write_pwl(key, self.prev_mask[i], self.mask[i])
        self.prev_mask = self.mask

        # # write sense_trig
        if self.read and increment_time:
            self.write_pwl("sense_trig", 0, 1)
            if not OPTS.baseline and increment_time:
                self.write_pwl("diff", 0, 1)
                self.write_pwl("diffb", 1, 0)

        super().update_output(increment_time)

        if self.read:
            self.write_pwl("sense_trig", 1, 0)
            if not OPTS.baseline and increment_time:
                self.write_pwl("diff", 1, 0)
                self.write_pwl("diffb", 0, 1)

    def baseline_read(self, address_int, comment=""):
        address_vec = self.convert_address(address_int)
        self.command_comments.append("* t = {} {} \n".format(self.current_time, comment))

        self.address = list(reversed(address_vec))

        self.acc_en = self.read = 1
        self.acc_en_inv = 0

        self.duty_cycle = self.read_duty_cycle
        self.period = self.read_period

        self.update_output()

    def baseline_write(self, address_int, data_vec, mask_vec, comment=""):
        address_vec = self.convert_address(address_int)
        self.command_comments.append("* t = {} {} \n".format(self.current_time, comment))
        self.mask = list(reversed(mask_vec))
        self.address = list(reversed(address_vec))
        self.data = list(reversed(data_vec))

        self.acc_en = self.read = 0
        self.acc_en_inv = 1

        self.duty_cycle = self.write_duty_cycle
        self.period = self.write_period

        self.update_output()

    def read_data(self, address_int, comment=""):
        """Read an address. Address is binary vector"""
        address_vec = self.convert_address(address_int)
        self.command_comments.append("* t = {} {} \n".format(self.current_time, comment))

        self.address = list(reversed(address_vec))

        self.read = 1

        self.diff = 1
        self.diffb = 0

        self.en_0 = 1
        self.en_1 = 0

        self.sr_en = 0

        self.set_selects(bus_sel="s_and")

        self.update_output()

    def write_masked_data(self, address_int, data_vec, mask_vec, comment=""):
        """Write data to an address. Data can be integer or binary vector. Address is binary vector"""
        self.setup_mask_measurements()
        address_vec = self.convert_address(address_int)
        self.command_comments.append("* t = {} {} \n".format(self.current_time, comment))
        self.mask = list(reversed(mask_vec))
        self.address = list(reversed(address_vec))
        self.data = list(reversed(data_vec))

        self.set_selects(bus_sel="s_data", sr_in="s_mask_in", sr_out="s_sr")

        self.read = 0

        self.sr_en = 1

        self.en_0 = 1
        self.en_1 = 0

        self.update_output()


    def write_back(self, address_int, bus_sel="s_sum", sr_in="s_mask_in", sr_out="s_sr", comment=""):
        self.setup_mask_measurements()
        address_vec = self.convert_address(address_int)
        self.command_comments.append("* t = {} {} \n".format(self.current_time, comment))
        self.address = list(reversed(address_vec))

        self.set_selects(bus_sel, sr_in, sr_out)

        self.read = 0

        self.sr_en = 1

        self.en_0 = 1
        self.en_1 = 0

        self.update_output()

    def write_shift_register(self, bus_sel="s_sum", sr_in="s_mask_in", sr_out="s_sr", comment=""):
        self.command_comments.append("* t = {} {} \n".format(self.current_time, comment))
        self.bank_sel = 0
        current_sr_en = self.sr_en
        self.sr_en = 1

        self.set_selects(bus_sel, sr_in, sr_out)
        self.update_output()
        self.bank_sel = 1
        self.sr_en = current_sr_en

    def bitline_compute(self, addr0, addr1, bus_sel="s_sum", sr_in="s_mask_in",
                        sr_out="s_sr", comment=""):
        self.command_comments.append("* t = {} Bitline ({}) + ({}) {} \n".format(self.current_time,
                                                                                 addr0, addr1, comment))
        self.address = list(reversed(self.convert_address(addr0)))
        self.address_1 = list(reversed(self.convert_address(addr1)))

        self.read = 1

        self.diff = 0
        self.diffb = 1

        self.en_0 = 1
        self.en_1 = 1

        self.set_selects(bus_sel, sr_in, sr_out)

        self.update_output()


    def set_selects(self, bus_sel=None, sr_in=None, sr_out=None):

        def one_hot_mux(selected, all_sels):
            if selected is None:  # to enable selective sets
                return
            assert selected in all_sels, "Selected {} must be in {}".format(selected, " ".join(all_sels))
            for sig in all_sels:
                if selected == sig:
                    value = 1
                else:
                    value = 0
                setattr(self, sig, value)

        if OPTS.serial:
            one_hot_mux(bus_sel, self.bus_selects)
            one_hot_mux(sr_in, self.sr_in_selects)
            # TODO mask_en set reminder
        else:
            selects = [self.bus_selects, self.sr_in_selects, self.sr_out_selects]
            selected = [bus_sel, sr_in, sr_out]
            for i in range(3):
                one_hot_mux(selected[i], selects[i])
    # uOPS
    def rd(self, addr):
        """Read an address. Address is binary vector"""
        addr_v = self.convert_address(addr)

        self.command_comments.append("* [{: >20}] rd {}\n".format(self.current_time, addr_v))

        self.address = list(reversed(addr_v))

        # Needed signals
        self.sel_bank = 1
        self.read = 1

        self.en_0 = 1
        self.en_1 = 0

        self.diff = 1
        self.diffb = 0

        if OPTS.serial:
            self.mask_en = 0
            self.sr_en   = 0
            self.s_cout  = 1
        else:
            self.sr_en   = 0

        self.set_selects(bus_sel="s_and")

        self.acc_en     = 0
        self.acc_en_inv = 1

        self.duty_cycle = self.read_duty_cycle
        self.period = self.read_period

        self.update_output()

        # Reset important signals
        self.sel_bank = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    def wr(self, addr, data_v, mask_v):
        """Write data to an address. Data can be integer or binary vector. Address is binary vector"""
        #self.setup_mask_measurements()

        addr_v = self.convert_address(addr)
        #data_v = self.convert_address(data)
        #mask_v = self.convert_address(mask)

        self.command_comments.append("* [{: >20}] wr {}, {}\n".format(self.current_time, addr_v, data_v))

        self.mask = list(reversed(mask_v))
        self.address = list(reversed(addr_v))
        self.data = list(reversed(data_v))

        self.set_selects(bus_sel="s_data", sr_in="s_mask_in", sr_out="s_sr")

        # Needed signals
        self.sel_bank = 1
        self.read = 0

        if OPTS.serial:
            self.mask_en = 1
            self.sr_en   = 0
            self.s_cout  = 1
        else:
            self.sr_en   = 1

        self.en_0 = 1
        self.en_1 = 0

        self.acc_en     = 0
        self.acc_en_inv = 1

        self.update_output()

        # Reset important signals
        self.sel_bank = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    def set_mask(self, mask_v):
        self.command_comments.append("* [{: >20}] set_mask {}\n".format(self.current_time, mask_v))

        self.mask = list(reversed(mask_v))

        self.set_selects(sr_in="s_mask_in")

        self.read = 0

        if OPTS.serial:
            self.mask_en = 1
            self.sr_en   = 0
            self.s_cout  = 1
        else:
            self.sr_en   = 1

        self.en_0 = 0
        self.en_1 = 0

        self.acc_en     = 0
        self.acc_en_inv = 1

        self.update_output()

        # Reset important signals
        self.sel_bank = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    def blc(self, addr0, addr1):
        addr0_v = self.convert_address(addr0)
        addr1_v = self.convert_address(addr1)

        self.command_comments.append("* [{: >20}] blc {}, {}\n".format(self.current_time, addr0_v, addr1_v))

        self.address   = list(reversed(self.convert_address(addr0_v)))
        self.address_1 = list(reversed(self.convert_address(addr1_v)))

        # Needed signals
        self.sel_bank = 1
        self.read = 1

        self.diff = 0
        self.diffb = 1

        self.en_0 = 1
        self.en_1 = 1

        if OPTS.serial:
            self.mask_en = 0
            self.sr_en   = 0
            self.s_cout  = 1
        else:
            self.sr_en   = 0

        #self.set_selects(bus_sel, sr_in, sr_out)

        self.acc_en     = 0
        self.acc_en_inv = 1

        self.update_output()

        # Reset important signals
        self.sel_bank = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    def wb(self, addr, src, cond):
        #self.setup_mask_measurements()

        addr_v = self.convert_address(addr)

        # Conditional Execution Selection
        if   cond == 'msb'   : cond_str = 'if_msb.'
        elif cond == 'lsb'   : cond_str = 'if_lsb.'
        else                 : cond_str = ''

        # Source Selection
        if   src == 'and'    : src_str = '.and'
        elif src == 'nand'   : src_str = '.nand'
        elif src == 'nor'    : src_str = '.nor'
        elif src == 'or'     : src_str = '.or'

        elif src == 'xor'    : src_str = '.xor'
        elif src == 'xnor'   : src_str = '.xnor'

        elif src == 'add'    : src_str = '.add'

        elif src == 'data_in': src_str = '.data_in'

        else                 : src_str = '.and'

        self.command_comments.append("* [{: >20}] {}wb{} {}\n".format(self.current_time, cond_str, src_str, addr_v))

        self.address = list(reversed(addr_v))
        self.mask = [1] * self.num_cols

        # Generate Signals
        if   src == 'and'    : bus_sel = 's_and'
        elif src == 'nand'   : bus_sel = 's_nand'
        elif src == 'nor'    : bus_sel = 's_nor'
        elif src == 'or'     : bus_sel = 's_or'

        elif src == 'xor'    : bus_sel = 's_xor'
        elif src == 'xnor'   : bus_sel = 's_xnor'

        elif src == 'add'    : bus_sel = 's_sum'

        elif src == 'data_in': bus_sel = 's_data'

        else                 : bus_sel = 's_and'


        # Conditionals/Masking Signals
        sr_en = 0

        if   cond == 'msb'   : pass
        elif cond == 'lsb'   : pass
        else                 : sr_en = 1; sr_in = 's_mask_in'

        if   cond == 'msb'   : sr_out = 's_msb'
        elif cond == 'lsb'   : sr_out = 's_lsb'
        else                 : sr_out = 's_sr'

        self.set_selects(bus_sel, sr_in, sr_out)

        # Needed signals
        self.sel_bank = 1
        self.read = 0

        self.en_0 = 1
        self.en_1 = 0

        self.acc_en     = 0
        self.acc_en_inv = 1

        if OPTS.serial:
            self.mask_en = sr_en
            self.sr_en   = 1 if src == 'add' else 0
            self.s_cout  = 1
        else:
            self.sr_en   = sr_en

        self.update_output()

        # Reset important signals
        self.sel_bank = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    # All possible variants
    def        wb_and    (self, addr): self.wb(addr, 'and'    , ''   )
    def if_msb_wb_and    (self, addr): self.wb(addr, 'and'    , 'msb')
    def if_lsb_wb_and    (self, addr): self.wb(addr, 'and'    , 'lsb')
    def        wb_nand   (self, addr): self.wb(addr, 'nand'   , ''   )
    def if_msb_wb_nand   (self, addr): self.wb(addr, 'nand'   , 'msb')
    def if_lsb_wb_nand   (self, addr): self.wb(addr, 'nand'   , 'lsb')
    def        wb_or     (self, addr): self.wb(addr, 'or'     , ''   )
    def if_msb_wb_or     (self, addr): self.wb(addr, 'or'     , 'msb')
    def if_lsb_wb_or     (self, addr): self.wb(addr, 'or'     , 'lsb')
    def        wb_nor    (self, addr): self.wb(addr, 'nor'    , ''   )
    def if_msb_wb_nor    (self, addr): self.wb(addr, 'nor'    , 'msb')
    def if_lsb_wb_nor    (self, addr): self.wb(addr, 'nor'    , 'lsb')

    def        wb_xor    (self, addr): self.wb(addr, 'xor'    , ''   )
    def if_msb_wb_xor    (self, addr): self.wb(addr, 'xor'    , 'msb')
    def if_lsb_wb_xor    (self, addr): self.wb(addr, 'xor'    , 'lsb')
    def        wb_xnor   (self, addr): self.wb(addr, 'xnor'   , ''   )
    def if_msb_wb_xnor   (self, addr): self.wb(addr, 'xnor'   , 'msb')
    def if_lsb_wb_xnor   (self, addr): self.wb(addr, 'xnor'   , 'lsb')

    def        wb_add    (self, addr): self.wb(addr, 'add'    , ''   )
    def if_msb_wb_add    (self, addr): self.wb(addr, 'add'    , 'msb')
    def if_lsb_wb_add    (self, addr): self.wb(addr, 'add'    , 'lsb')
    def        wb_data_in(self, addr): self.wb(addr, 'data_in', ''   )
    def if_msb_wb_data_in(self, addr): self.wb(addr, 'data_in', 'msb')
    def if_lsb_wb_data_in(self, addr): self.wb(addr, 'data_in', 'lsb')

    # Shift-Register
    def srl(self):
        self.command_comments.append("* [{: >20}] srl\n".format(self.current_time))

        self.set_selects(sr_in = 's_shift')

        self.sr_in = 1

        self.read = 0
        self.en_0 = 0
        self.en_1 = 0

        self.acc_en     = 0
        self.acc_en_inv = 1

        self.update_output()

        # Reset important signals
        self.sel_bank = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    # CIN
    def set_cin(self, val):
        val = [0] * len(self.c_val)

        self.c_val = val

        self.sr_en = 1

        self.read = 0
        self.en_0 = 0
        self.en_1 = 0

        self.acc_en     = 0
        self.acc_en_inv = 1

        self.update_output()

        # Reset important signals
        self.sel_bank = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    def wb_mask(self, src):
        #self.setup_mask_measurements()

        # Source Selection
        if   src == 'and'    : src_str = '.and'
        elif src == 'nand'   : src_str = '.nand'
        elif src == 'nor'    : src_str = '.nor'
        elif src == 'or'     : src_str = '.or'

        elif src == 'xor'    : src_str = '.xor'
        elif src == 'xnor'   : src_str = '.xnor'

        elif src == 'add'    : src_str = '.add'

        elif src == 'data_in': src_str = '.data_in'

        else                 : src_str = '.and'

        self.command_comments.append("* [{: >20}] wb_mask{}\n".format(self.current_time, src_str))

        # Generate Signals
        sr_in = 's_bus'

        if   src == 'and'    : bus_sel = 's_and'
        elif src == 'nand'   : bus_sel = 's_nand'
        elif src == 'nor'    : bus_sel = 's_nor'
        elif src == 'or'     : bus_sel = 's_or'

        elif src == 'xor'    : bus_sel = 's_xor'
        elif src == 'xnor'   : bus_sel = 's_xnor'

        elif src == 'add'    : bus_sel = 's_sum'

        elif src == 'data_in': bus_sel = 's_data'

        else                 : bus_sel = 's_and'

        self.set_selects(bus_sel = bus_sel, sr_in = sr_in)

        if OPTS.serial:
            self.mask_en = 1
            self.sr_en   = 0
            self.s_cout  = 1
        else:
            self.sr_en   = 1

        self.read = 0
        self.en_0 = 0
        self.en_1 = 0

        self.acc_en     = 0
        self.acc_en_inv = 1

        self.update_output()

        # Reset important signals
        self.sel_bank = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    # All possible variants
    def wb_mask_and    (self): self.wb(0, 'and'    , '')
    def wb_mask_nand   (self): self.wb(0, 'nand'   , '')
    def wb_mask_or     (self): self.wb(0, 'or'     , '')
    def wb_mask_nor    (self): self.wb(0, 'nor'    , '')

    def wb_mask_xor    (self): self.wb(0, 'xor'    , '')
    def wb_mask_xnor   (self): self.wb(0, 'xnor'   , '')

    def wb_mask_add    (self): self.wb(0, 'add'    , '')
    def wb_mask_data_in(self): self.wb(0, 'data_in', '')

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
     # Macro-Operations
    def add(self):
        num_cols = self.num_cols
        word_size = self.word_size

        def select_cols(x):
            if len(x) >= num_cols:
                return x[:num_cols]
            else:
                repeats = ceil(num_cols/len(x))
                return (x*repeats)[:num_cols]

        data_one = select_cols([0]*word_size + [1, 0, 0, 1]*int(word_size/4))
        data_two = select_cols([0]*(word_size-1) + [1] + [1, 0, 1, 0]*int(word_size/4))
        data_three = select_cols([1] * word_size + [1, 1, 0, 0] * int(word_size / 4))

        mask_all = select_cols([1] * (2 * word_size))

        bit_sz  = int(32 / 8)
        MAX_INT = 1 << bit_sz

        A = [random.randint(0, MAX_INT - 1) for i in range(32)]
        B = [random.randint(0, MAX_INT - 1) for i in range(32)]

        C = []
        for a, b in zip(A, B):
            C += [a + b]

        verify_C = [0 for i in range(32)]

        # Load Data
        addr_A = 0 * bit_sz
        addr_B = 1 * bit_sz
        addr_C = 2 * bit_sz

        self.set_cin(0)

        for bit in range(0, bit_sz):
            mask   = 1 << bit
            # A
            data_A = []
            for i in range(32):
                val     = 1 if (A[i] & mask) != 0 else 0
                data_A += [val]

            # B
            data_B = []
            for i in range(32):
                val     = 1 if (B[i] & mask) != 0 else 0
                data_B += [val]

            # Write data
            self.wr(bit + addr_A, data_A, mask_all)
            self.wr(bit + addr_B, data_B, mask_all)

        # Add two numbers
        for i in range(bit_sz):
          self.blc(addr_A + i, addr_B + i)
          self.wb_add(addr_C + i)

        verify_file = open("verify.data", "w")
        # Verify
        for bit in range(0, bit_sz):
            mask   = 1 << bit

            # Read
            self.rd(addr_C + bit)

            # Parse
           #mask   = 1 << bit

            # A
            data_C = []
            for i in range(32):
                val     = 1 if (C[i] & mask) != 0 else 0
                data_C += [val]

            self.command_comments.append("* expected = {}\n".format(data_C))
            verify_file.write("[{}, {}],\n".format(self.current_time, data_C))

        verify_file.close()

    def test_wr_rd(self):
        num_cols = self.num_cols
        word_size = self.word_size

        def select_cols(x):
            if len(x) >= num_cols:
                return x[:num_cols]
            else:
                repeats = ceil(num_cols/len(x))
                return (x*repeats)[:num_cols]

        data_one = select_cols([0]*word_size + [1, 0, 0, 1]*int(word_size/4))
        data_two = select_cols([0]*(word_size-1) + [1] + [1, 0, 1, 0]*int(word_size/4))
        data_three = select_cols([1] * word_size + [1, 1, 0, 0] * int(word_size / 4))

        mask_all = select_cols([1] * (2 * word_size))

        bit_sz  = int(32 / 8)
        MAX_INT = 1 << bit_sz

        # Load Data
        verify_file = open("verify.data", "w")
        verify_data = []
        for addr in range(0, 8):
            data = self.get_random_bin_vector(32)

            # Write data
            self.wr(addr, data, mask_all)

            # Remember
            verify_data += data


        for data in verify_data:
            # Read the data
            verify_file.write("[{}, {}],\n".format(self.current_time + 1.9, data))
            self.rd(addr)

        verify_file.close()

    def test_blc(self):
        num_cols = self.num_cols
        word_size = self.word_size

        def select_cols(x):
            if len(x) >= num_cols:
                return x[:num_cols]
            else:
                repeats = ceil(num_cols/len(x))
                return (x*repeats)[:num_cols]

        data_one = select_cols([0]*word_size + [1, 0, 0, 1]*int(word_size/4))
        data_two = select_cols([0]*(word_size-1) + [1] + [1, 0, 1, 0]*int(word_size/4))
        data_three = select_cols([1] * word_size + [1, 1, 0, 0] * int(word_size / 4))

        mask_all = select_cols([1] * (2 * word_size))

        bit_sz  = int(32 / 8)
        MAX_INT = 1 << bit_sz

        # Load Data
        verify_file = open("verify.data", "w")
        verify_data = []
        for addr in range(0, 2):
            data = self.get_random_bin_vector(32)

            # Write data
            self.wr(addr, data, mask_all)

            # Remember
            verify_data.append([addr, data])

        for entry in verify_data:
            addr = entry[0]
            data = entry[1]

            # Read the data
            self.blc(addr, addr)

            verify_file.write("[{}, {}],\n".format(self.current_time + 1.9, data))
            self.wb_and(addr)

        verify_file.close()

    def setup_write_measurements(self, address_int):
        """new_val is MSB first"""
        time = self.current_time
        # power measurement
        time_suffix = "{:.2g}".format(time).replace('.', '_')
        meas_name = "WRITE_POWER_t{}".format(time_suffix)
        self.stim.gen_meas_power(meas_name=meas_name,
                                 t_initial=time - self.setup_time,
                                 t_final=time + self.period - self.setup_time)
        # decoder delay
        self.setup_decoder_delays()

        # Internal bitcell Q state transition delay
        state_labels = self.state_probes[address_int]
        for i in range(self.word_size):
            targ_val = 0.5*self.vdd_voltage
            targ_dir = "CROSS"

            meas_name = "STATE_DELAY_a{}_c{}_t{}".format(address_int, i, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name=self.clk_buf_probe, trig_val=0.5 * self.vdd_voltage, trig_dir="FALL",
                                     trig_td=time + self.duty_cycle*self.period,
                                     targ_name=state_labels[i], targ_val=targ_val, targ_dir=targ_dir,
                                     targ_td=time + self.duty_cycle*self.period)

    def setup_decoder_delays(self):
        for address_int, decoder_label in self.decoder_probes.items():
            time_suffix = "{:.2g}".format(self.current_time).replace('.', '_')
            meas_name = "decoder_a{}_t{}".format(address_int, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name=self.clk_buf_probe, trig_val=0.5*self.vdd_voltage, trig_dir="RISE",
                                     trig_td=self.current_time,
                                     targ_name=decoder_label, targ_val=0.5*self.vdd_voltage, targ_dir="CROSS",
                                     targ_td=self.current_time)

    def setup_mask_measurements(self):
        for col, col_label in self.mask_probes.items():
            time_suffix = "{:.2g}".format(self.current_time).replace('.', '_')
            meas_name = "mask_col{}_t{}".format(col, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name=self.clk_buf_probe, trig_val=0.5*self.vdd_voltage, trig_dir="RISE",
                                     trig_td=self.current_time,
                                     targ_name=col_label, targ_val=0.5*self.vdd_voltage, targ_dir="CROSS",
                                     targ_td=self.current_time)

    def setup_precharge_measurement(self):
        time = self.current_time
        # power measurement
        time_suffix = "{:.2g}".format(time).replace('.', '_')
        targ_val = 0.5 * self.vdd_voltage
        for i in range(self.word_size):
            for bitline in ["bl", "br"]:
                if bitline == "br":
                    probe = self.bitline_probes[i]
                else:
                    probe = self.br_probes[i]
                meas_name = "PRECHARGE_DELAY_{}_c{}_t{}".format(bitline, i, time_suffix)
                self.stim.gen_meas_delay(meas_name=meas_name,
                                         trig_name=self.clk_buf_probe, trig_val=targ_val, trig_dir="RISE",
                                         trig_td=time,
                                         targ_name=probe, targ_val=targ_val, targ_dir="RISE",
                                         targ_td=time)

    def setup_read_measurements(self, address_int):
        """new_val is MSB first"""

        self.setup_precharge_measurement()

        time = self.current_time
        # power measurement
        time_suffix = "{:.2g}".format(time).replace('.', '_')
        meas_name = "READ_POWER_t{}".format(time_suffix)
        self.stim.gen_meas_power(meas_name=meas_name,
                                 t_initial=time - self.setup_time,
                                 t_final=time + self.period - self.setup_time)
        # decoder delay
        self.setup_decoder_delays()

        # Data bus transition delay
        for i in range(self.word_size):
            targ_val = 0.5 * self.vdd_voltage

            meas_name = "READ_DELAY_a{}_c{}_t{}".format(address_int, i, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name=self.clk_buf_probe, trig_val=0.5 * self.vdd_voltage, trig_dir="FALL",
                                     trig_td=time + self.duty_cycle * self.period,
                                     targ_name=self.dout_probes[i], targ_val=targ_val, targ_dir="CROSS",
                                     targ_td=time + self.duty_cycle * self.period)

    def write_generic_stimulus(self):
        """ Overrides super class method to use internal logic for measurement setup
        Create the sram instance, supplies
         """

        # add vdd/gnd statements
        self.sf.write("\n* Global Power Supplies\n")
        self.stim.write_supply()

        # instantiate the sram
        self.sf.write("\n* Instantiation of the SRAM\n")
        self.stim.inst_sram(abits=self.addr_size,
                            dbits=self.word_size,
                            sram_name=self.name)

        self.stim.inst_accesstx(self.word_size)

    def run_drc_lvs_pex(self):
        OPTS.check_lvsdrc = True
        reload(verify)

        self.sram.sp_write(OPTS.spice_file)
        self.sram.gds_write(OPTS.gds_file)

        if getattr(OPTS, 'run_drc', True):
            drc_result = verify.run_drc(self.sram.name, OPTS.gds_file, exception_group="sram")
            if drc_result:
                raise AssertionError("DRC Failed")
        else:

            from base import utils
            utils.to_cadence(OPTS.gds_file)

        if getattr(OPTS, 'run_lvs', True):
            lvs_result = verify.run_lvs(self.sram.name, OPTS.gds_file, OPTS.spice_file,
                                        final_verification=True)
            if lvs_result:
                raise AssertionError("LVS Failed")

        if OPTS.use_pex and getattr(OPTS, 'run_pex', True):
            if getattr(OPTS, 'top_level_pex', True):
                errors = verify.run_pex(self.sram.name, OPTS.gds_file, OPTS.spice_file, OPTS.pex_spice)
                if errors:
                    raise AssertionError("PEX failed")
            else:
                modules = getattr(OPTS, 'pex_submodules', [])
                for module in modules:
                    spice_name = os.path.join(OPTS.openram_temp, module.name + "_sub.sp")
                    gds_name = os.path.join(OPTS.openram_temp, module.name + "_sub.gds")
                    pex_name = os.path.join(OPTS.openram_temp, module.name + "_pex.sp")

                    module.sp_write(spice_name)
                    module.gds_write(gds_name)

                    errors = verify.run_pex(module.name, gds_name, spice_name, pex_name)
                    if errors:
                        raise AssertionError("PEX failed")
