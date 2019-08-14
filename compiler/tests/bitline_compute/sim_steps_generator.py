import os
from importlib import reload

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

    baseline_sim = False

    def __init__(self, sram, spfile, corner, initialize=False):
        super().__init__(sram, spfile, corner, initialize=initialize)

        # set up for write
        self.read = self.prev_read = 0
        self.en_0 = self.prev_en_0 = 1
        self.en_1 = self.prev_en_1 = 0
        self.mask = self.prev_mask = [1] * OPTS.word_size
        mid_address = int(0.5*self.sram.num_words)
        self.address_1 = self.prev_address_1 = self.convert_address(mid_address)

        for i in range(self.addr_size):
            self.bus_sigs.append("A_1[{}]".format(i))

        for i in range(self.word_size):
            self.bus_sigs.append("mask[{}]".format(i))

        self.control_sigs = ["read", "en_0", "en_1", "acc_en", "acc_en_inv"]

    def write_delay_stimulus(self):
        """ Override super class method to use internal logic for pwl voltages and measurement setup
         Creates a stimulus file for simulations to probe a bitcell at a given clock period.
        """

        reload(characterizer)

        # creates and opens stimulus file for writing
        self.current_time = 0
        temp_stim = os.path.join(OPTS.openram_temp, "stim.sp")
        self.sf = open(temp_stim, "w")
        self.sf.write("{} \n".format(self.sram))
        if OPTS.spice_name == "spectre":
            self.sf.write("simulator lang=spice\n")
        self.sf.write("* Delay stimulus for read period = {0}n, write period = {1} load={2}fF slew={3}ns\n\n".format(
            self.read_period, self.write_period, self.load, self.slew))

        self.stim = SpiceDut(self.sf, self.corner)

        self.write_generic_stimulus()

        if not self.baseline_sim:
            self.stim.gen_constant("sense_amp_ref", OPTS.sense_amp_ref, gnd_node="gnd")

        self.initialize_output()

        self.generate_steps()

        for node in self.saved_nodes:
            self.sf.write(".probe V({0}) \n".format(node))

        self.finalize_output()

        self.stim.write_include(self.trim_sp_file)

        # run until the end of the cycle time
        self.stim.write_control(self.current_time + self.period)

        self.sf.close()

    def probe_addresses(self, addresses):
        probe = BlProbe(self.sram, OPTS.pex_spice)
        probe.probe_outputs()

        probe.probe_bitlines(0)
        probe.probe_misc_bank(0)

        for address in addresses:
            probe.probe_address(address)

        self.run_drc_lvs_pex()

        probe.extract_probes()

        self.and_probes = probe.and_probes
        self.nor_probes = probe.nor_probes
        self.state_probes = probe.state_probes
        self.decoder_probes = probe.decoder_probes
        self.dout_probes = probe.dout_probes
        self.bitline_probes = probe.bitline_probes

        return probe

    def generate_steps(self):
        """
        Given address A, B, C
        First test read and write operations:

        Write zeros to A then ones to A again observe transition in bitcell
        Write zeros to C to reset decoder, also used for bitline computation
        Write zeros to B which means data bus is now zero
        Read address A which should set data bus to ones ensuring transition in data bus

        For bitline compute
        From previous read, AND's will be ones and NORs will be zeros
        For transition in AND's, bitline compute A and B (NORs still zeros)
        For transition in NOR's, bitline compute B and C (NORs will become ones)
        """

        # TODO addresses to use?
        a_address = 0
        b_address = self.sram.num_words - 1
        c_address = 1
        probe = self.probe_addresses([a_address, b_address, c_address])

        zero_data = [0]*self.word_size
        one_data = [1]*self.word_size

        mask = [1] * self.word_size

        self.write_masked_data(self.convert_address(a_address), zero_data, mask, "Set A to zero")
        self.write_masked_data(self.convert_address(c_address), zero_data, mask, "Set C to zero")

        self.setup_write_measurements(a_address, one_data)
        self.write_masked_data(self.convert_address(a_address), one_data, mask, "Set A to ones")

        self.write_masked_data(self.convert_address(b_address), zero_data, mask, "Set B to zero")

        self.setup_read_measurements(a_address, one_data)
        self.read_data(self.convert_address(a_address), "Read A")

        if not self.baseline_sim:
            self.setup_and_measurement(one_data, zero_data)
            self.bitline_compute(a_address, b_address, "Bitline A and B")

            self.setup_nor_measurement(zero_data, zero_data)
            self.bitline_compute(b_address, c_address, "Bitline B and C")

        self.saved_nodes = sorted(probe.saved_nodes)

    @staticmethod
    def invert_vec(data_vec):
        return [0 if x == 1 else 1 for x in data_vec]

    @staticmethod
    def probe_matchlines(probe, cam):
        for i in range(cam.num_words):
            probe.probe_matchline(i)

    def update_output(self):
        # write address1
        for i in range(self.addr_size):
            key = "A_1[{}]".format(i)
            self.write_pwl(key, self.prev_address_1[i], self.address_1[i])
        self.prev_address_1 = self.address_1
        # write mask
        for i in range(self.word_size):
            key = "mask[{}]".format(i)
            self.write_pwl(key, self.prev_mask[i], self.mask[i])
        self.prev_mask = self.mask
        super().update_output()

    def read_data(self, address_vec, comment=""):
        """Read an address. Address is binary vector"""
        self.command_comments.append("* t = {} Read {} \n".format(self.current_time, address_vec))

        self.address = list(reversed(address_vec))

        self.acc_en = self.read = 1
        self.acc_en_inv = 0
        self.en_0 = 1
        self.en_1 = 0

        self.duty_cycle = self.read_duty_cycle
        self.period = self.read_period

        self.update_output()

    def write_masked_data(self, address_vec, data_vec, mask_vec, comment=""):
        """Write data to an address. Data can be integer or binary vector. Address is binary vector"""
        self.command_comments.append("* t = {} Write {} to {} {} \n".format(self.current_time, data_vec,
                                                                            address_vec, comment))
        self.mask = list(reversed(mask_vec))
        self.address = list(reversed(address_vec))
        self.data = list(reversed(data_vec))

        self.acc_en = self.read = 0
        self.acc_en_inv = 1

        self.en_0 = 1
        self.en_1 = 0

        self.duty_cycle = self.write_duty_cycle
        self.period = self.write_period

        self.update_output()

    def bitline_compute(self, addr0, addr1, comment=""):
        self.command_comments.append("* t = {} Bitline Compute {} and {} {} \n".format(self.current_time,
                                                                                       addr0, addr1, comment))
        self.address = list(reversed(self.convert_address(addr0)))
        self.address_1 = list(reversed(self.convert_address(addr1)))

        self.read = 1
        self.en_0 = 1
        self.en_1 = 1

        self.duty_cycle = self.read_duty_cycle
        self.period = self.read_period

        self.update_output()

    def setup_write_measurements(self, address_int, new_val):
        """new_val is MSB first"""
        time = self.current_time
        # power measurement
        time_suffix = "{:.2g}".format(time).replace('.', '_')
        meas_name = "WRITE_POWER_t{}".format(time_suffix)
        self.stim.gen_meas_power(meas_name=meas_name,
                                 t_initial=time - self.setup_time,
                                 t_final=time + self.period - self.setup_time)
        # decoder delay
        decoder_label = self.decoder_probes[address_int]
        self.stim.gen_meas_delay(meas_name="decoder_a{}_t{}".format(address_int, time_suffix),
                                 trig_name="clk", trig_val=0.9 * self.vdd_voltage, trig_dir="RISE",
                                 trig_td=time,
                                 targ_name=decoder_label, targ_val=0.9 * self.vdd_voltage, targ_dir="RISE",
                                 targ_td=time)

        # Internal bitcell Q state transition delay
        state_labels = self.state_probes[address_int]
        new_val_reversed = list(reversed(new_val))
        for i in range(self.word_size):
            transition = "HL" if new_val_reversed[i] == 0 else "LH"
            targ_val = 0.9*self.vdd_voltage if transition == "LH" else 0.1*self.vdd_voltage
            targ_dir = "RISE" if transition == "LH" else "FALL"

            meas_name = "STATE_DELAY_a{}_c{}_t{}".format(address_int, i, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name="clk", trig_val=0.1 * self.vdd_voltage, trig_dir="FALL",
                                     trig_td=time + self.duty_cycle*self.period,
                                     targ_name=state_labels[i], targ_val=targ_val, targ_dir=targ_dir,
                                     targ_td=time + self.duty_cycle*self.period)

    def setup_precharge_measurement(self):
        time = self.current_time
        # power measurement
        time_suffix = "{:.2g}".format(time).replace('.', '_')
        for i in range(self.word_size):
            targ_val = 0.9 * self.vdd_voltage
            targ_dir = "RISE"

            meas_name = "PRECHARGE_DELAY_c{}_t{}".format(i, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name="clk", trig_val=targ_val, trig_dir="RISE",
                                     trig_td=time,
                                     targ_name=self.bitline_probes[i], targ_val=targ_val, targ_dir=targ_dir,
                                     targ_td=time)

    def setup_read_measurements(self, address_int, expected_val):
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
        decoder_label = self.decoder_probes[address_int]
        self.stim.gen_meas_delay(meas_name="decoder_a{}_t{}".format(address_int, time_suffix),
                                 trig_name="clk", trig_val=0.9 * self.vdd_voltage, trig_dir="RISE",
                                 trig_td=time,
                                 targ_name=decoder_label, targ_val=0.9 * self.vdd_voltage, targ_dir="RISE",
                                 targ_td=time)

        # Data bus transition delay
        expected_val_reversed = list(reversed(expected_val))
        for i in range(self.word_size):
            transition = "HL" if expected_val_reversed[i] == 0 else "LH"
            targ_val = 0.9 * self.vdd_voltage if transition == "LH" else 0.1 * self.vdd_voltage
            targ_dir = "RISE" if transition == "LH" else "FALL"

            meas_name = "READ_DELAY_a{}_c{}_t{}".format(address_int, i, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name="clk", trig_val=0.1 * self.vdd_voltage, trig_dir="FALL",
                                     trig_td=time + self.duty_cycle * self.period,
                                     targ_name=self.dout_probes[i], targ_val=targ_val, targ_dir=targ_dir,
                                     targ_td=time + self.duty_cycle * self.period)

    def setup_and_measurement(self, data_0, data_1):

        self.setup_precharge_measurement()

        data_0 = list(reversed(data_0))
        data_1 = list(reversed(data_1))

        time = self.current_time
        time_suffix = "{:.2g}".format(time).replace('.', '_')

        for col in range(self.word_size):
            expected = data_0[col] and data_1[col]
            transition = "HL" if expected == 0 else "LH"
            targ_val = 0.9 * self.vdd_voltage if transition == "LH" else 0.1 * self.vdd_voltage
            targ_dir = "RISE" if transition == "LH" else "FALL"

            meas_name = "AND_DELAY_c{}_t{}".format(col, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name="clk", trig_val=0.1 * self.vdd_voltage, trig_dir="FALL",
                                     trig_td=time + self.duty_cycle * self.period,
                                     targ_name=self.and_probes[col], targ_val=targ_val, targ_dir=targ_dir,
                                     targ_td=time + self.duty_cycle * self.period)

    def setup_nor_measurement(self, data_0, data_1):

        self.setup_precharge_measurement()

        data_0 = list(reversed(data_0))
        data_1 = list(reversed(data_1))

        time = self.current_time
        # power measurement
        time_suffix = "{:.2g}".format(time).replace('.', '_')

        for col in range(self.word_size):
            expected = not(data_0[col] or data_1[col])
            transition = "HL" if expected == 0 else "LH"
            targ_val = 0.9 * self.vdd_voltage if transition == "LH" else 0.1 * self.vdd_voltage
            targ_dir = "RISE" if transition == "LH" else "FALL"

            meas_name = "NOR_DELAY_c{}_t{}".format(col, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name="clk", trig_val=0.1 * self.vdd_voltage, trig_dir="FALL",
                                     trig_td=time + self.duty_cycle * self.period,
                                     targ_name=self.nor_probes[col], targ_val=targ_val, targ_dir=targ_dir,
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
                                        final_verification=not self.separate_vdd)
            if lvs_result:
                raise AssertionError("LVS Failed")

        if OPTS.use_pex and getattr(OPTS, 'run_pex', True):
            errors = verify.run_pex(self.sram.name, OPTS.gds_file, OPTS.spice_file, OPTS.pex_spice)
            if errors:
                raise AssertionError("PEX failed")
