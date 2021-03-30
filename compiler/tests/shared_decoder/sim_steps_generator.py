import json
import os
from importlib import reload
from random import randint

import numpy as np

import characterizer
from characterizer.sequential_delay import SequentialDelay
from globals import OPTS
from shared_probe import SharedProbe
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

        self.two_bank_push = OPTS.push and self.sram.num_banks == 2
        self.is_cmos = OPTS.baseline or OPTS.push

        for i in range(self.word_size):
            self.bus_sigs.append("mask[{}]".format(i))

        self.control_sigs = ["web", "acc_en", "acc_en_inv", "sense_trig", "csb"]
        if "precharge_trig" in self.sram.pins:
            self.control_sigs.append("precharge_trig")

        self.words_per_row = self.sram.words_per_row

        self.sense_trig = self.prev_sense_trig = 0
        self.precharge_trig = self.prev_precharge_trig = 0
        self.csb = self.prev_csb = 0
        self.web = self.prev_web = 0
        self.read = 1
        self.chip_enable = 1

        self.mask = self.prev_mask = [1] * self.word_size

        mid_address = int(0.5 * self.sram.num_rows)
        self.address_1 = self.prev_address_1 = self.convert_address(mid_address)

    def write_pwl(self, key, prev_val, curr_val):
        """Append current time's data to pwl. Transitions from the previous value to the new value using the slew"""

        if prev_val == curr_val and self.current_time > 1.5 * self.period:
            return

        if key in ["clk"]:
            setup_time = 0
        elif key in ["acc_en", "acc_en_inv"]:  # to prevent contention with tri-state buffer
            setup_time = -0.75 * self.duty_cycle * self.period
        elif key == "sense_trig":
            trigger_delay = OPTS.sense_trigger_delay
            if prev_val == 0:
                setup_time = -(self.duty_cycle * self.period + trigger_delay)
            else:
                # This adds some delay to enable tri-state driver
                # For differential sense amp, give some window so data can be read
                setup_time = -(self.slew + OPTS.sense_trigger_setup)
        elif key == "precharge_trig":
            trigger_delay = OPTS.precharge_trigger_delay
            if prev_val == 1:
                setup_time = -trigger_delay + self.period
            else:
                setup_time = 0
        else:
            setup_time = self.setup_time

        t2 = max(self.slew, self.current_time + 0.5 * self.slew - setup_time)
        t1 = max(0.0, self.current_time - 0.5 * self.slew - setup_time)
        self.v_data[key] += " {0:8.8g}n {1}v {2:8.8g}n {3}v ".format(t1, self.vdd_voltage * prev_val, t2,
                                                           self.vdd_voltage * curr_val)
        self.v_comments[key] += " ({0}, {1}) ".format(int(self.current_time / self.period),
                                                      curr_val)

    def initialize_sim_file(self):
        """ Override super class method to use internal logic for pwl voltages and measurement setup
         Creates a stimulus file for simulations to probe a bitcell at a given clock period.
        """
        reload(characterizer)

        # creates and opens stimulus file for writing
        self.current_time = 0
        if not getattr(self, "sf", None):
            temp_stim = os.path.join(OPTS.openram_temp, "stim.sp")
            self.sf = open(temp_stim, "w")
        if OPTS.spice_name == "spectre":
            self.sf.write("// {} \n".format(self.sram))
            self.sf.write("simulator lang=spice\n")
        self.sf.write("* Delay stimulus.\n * Area={0:.0f}um2 load={1}fF slew={2}n\n\n".format(
            (self.sram.width * self.sram.height), self.load, self.slew))

        self.sf.write("* Probe cols = [{}]\n".format(",".join(map(str, OPTS.probe_cols))))

        self.stim = SpiceDut(self.sf, self.corner)
        self.stim.words_per_row = self.words_per_row

        self.write_generic_stimulus()

        self.initialize_output()

        self.probe = SharedProbe(self.sram, OPTS.pex_spice)
        self.probe.bitcell_probes = self.probe.state_probes

    def finalize_sim_file(self):
        self.saved_nodes = list(sorted(list(self.probe.saved_nodes) + list(self.dout_probes.values())
                                       + list(self.mask_probes.values())))

        self.saved_nodes.append(self.clk_buf_probe)

        self.saved_currents = self.probe.current_probes

        for node in self.saved_nodes:
            self.sf.write(".probe tran V({0}) \n".format(node))
        self.sf.write(".probe v(vvdd)\n")
        self.sf.write(".probe I(vvdd)\n")

        # if OPTS.spice_name == "spectre":
        #     self.sf.write("simulator lang=spectre \n")
        #     for node in self.saved_currents:
        #         self.sf.write("save {0} \n".format(node))
        #     self.sf.write("simulator lang=spice \n")
        # else:
        #     for node in self.saved_currents:
        #         self.sf.write(".probe tran I1({0}) \n".format(node))

        for node in self.saved_currents:
            self.sf.write(".probe tran I1({0}) \n".format(node))

        self.finalize_output()

        self.stim.write_include(self.trim_sp_file)
        self.stim.replace_bitcell(self.sram)

        # run until the end of the cycle time
        # Note run till at least one half cycle, this is because operations blend into each other
        self.stim.write_control(self.current_time + self.duty_cycle * self.period)

        self.sf.close()

        # save state probes
        state_probe_file = os.path.join(OPTS.openram_temp, "state_probes.json")
        with open(state_probe_file, "w") as f:
            json.dump(self.probe.state_probes, f, indent=4, sort_keys=True)

    def probe_bank(self, bank):
        if self.two_bank_push and bank == 1:
            self.probe.probe_bitlines(bank, col_offset=self.sram.num_cols)
        else:
            self.probe.probe_bitlines(bank)
        self.probe.probe_write_drivers(bank)
        self.probe.probe_latched_sense_amps(bank)
        self.probe.probe_misc_bank(bank)
        self.probe.probe_bank_currents(bank)

    def probe_addresses(self, addresses, bank=0):

        for address in addresses:
            address = self.offset_address_by_bank(address, bank)
            self.probe.probe_address(address)
            self.probe.probe_address_currents(address)

    def run_pex_and_extract(self):
        self.run_drc_lvs_pex()

        self.probe.extract_probes()

        self.state_probes = self.probe.state_probes
        self.decoder_probes = self.probe.decoder_probes
        self.clk_buf_probe = self.probe.clk_buf_probe
        self.dout_probes = self.probe.dout_probes
        self.mask_probes = self.probe.mask_probes

        self.bitline_probes = self.probe.bitline_probes
        self.br_probes = self.probe.br_probes

    def generate_energy_stimulus(self):
        num_sims = OPTS.energy
        # num_sims = 1
        mask = [1] * self.word_size

        ops = ["read", "write"]
        for i in range(num_sims):
            address = randint(0, self.sram.num_words - 1)

            op = ops[randint(0, 1)]
            if op == "read":
                self.read_address(address)
            else:
                data = [randint(0, 1) for x in range(self.word_size)]
                self.write_address(address, data, mask)
            self.sf.write("* -- {}: t = {:.5g} period = {}\n".format(op.upper(), self.current_time - self.period,
                                                                     self.period))
        self.current_time += 2*self.period  # to cool off from previous event
        self.period = max(self.read_period, self.write_period)
        self.chip_enable = 0
        self.update_output()

        # clock gating
        leakage_cycles = 10
        start_time = self.current_time
        end_time = leakage_cycles * self.read_period + start_time
        self.current_time = end_time

        self.sf.write("* -- LEAKAGE start = {:.5g} end = {:.5g}\n".format(start_time, self.current_time))

        self.sf.write("* --clk_buf_probe={}--\n".format(self.probe.clk_buf_probe))

    def test_address(self, address, bank, dummy_address=None, data=None, mask=None):
        address = self.offset_address_by_bank(address, bank)
        if dummy_address is None:
            dummy_address = 1 if not address == 1 else 2
        dummy_address = self.offset_address_by_bank(dummy_address, bank)

        bank_index, _, row, col_index = self.probe.decode_address(address)

        assert bank_index == bank

        self.sf.write("* -- Address Test: Addr, Row, Col, bank, time, per_r, per_w, duty_r, duty_w ")
        self.sf.write("* [{0}, {1}, {2}, {3}, {4}, {5}, {6}, {7}, {8}]\n".
                      format(address, row, col_index, bank, self.current_time, self.read_period,
                             self.write_period, self.read_duty_cycle, self.write_duty_cycle))

        if mask is None:
            mask = [1] * self.word_size
        if data is None:
            data = [1, 0] * int(self.word_size / 2)

        data_bar = [int(not x) for x in data]

        self.setup_write_measurements(address)
        self.write_address(address, data_bar, mask)

        if not self.is_cmos:
            # give enough time to settle before timed read
            self.write_address(dummy_address, data, mask)
            self.write_address(dummy_address, data, mask)
        self.setup_read_measurements(address)
        self.read_address(address)

        self.setup_write_measurements(address)
        self.write_address(address, data, mask)

        # write data_bar to force transition on the data bus
        self.write_address(dummy_address, data_bar, mask)

        if not self.is_cmos:
            # give enough time to settle before timed read
            self.write_address(dummy_address, data_bar, mask)
        self.setup_read_measurements(address)
        self.read_address(address)

    def offset_address_by_bank(self, address, bank):
        assert type(address) == int and bank < self.num_banks
        if OPTS.push and self.num_banks == 2:
            return address
        address += bank * int(2 ** self.sram.bank_addr_size)
        return address

    @staticmethod
    def invert_vec(data_vec):
        return [0 if x == 1 else 1 for x in data_vec]

    @staticmethod
    def probe_matchlines(probe, cam):
        for i in range(cam.num_words):
            probe.probe_matchline(i)

    def update_output(self, increment_time=True):
        # bank_sel
        self.csb = not self.chip_enable
        self.web = self.read

        # write mask
        for i in range(self.word_size):
            key = "mask[{}]".format(i)
            self.write_pwl(key, self.prev_mask[i], self.mask[i])
        self.prev_mask = self.mask

        # # write sense_trig
        if self.read and increment_time:
            self.write_pwl("sense_trig", 0, 1)

        if increment_time:
            self.write_pwl("precharge_trig", 0, 1)

        super().update_output(increment_time)

        if self.read:
            self.write_pwl("sense_trig", 1, 0)

        if increment_time:
            self.write_pwl("precharge_trig", 1, 0)

    def read_address(self, addr):
        """Read an address. Address is binary vector"""
        addr_v = self.convert_address(addr)

        self.command_comments.append("* [{: >20}] read {}\n".format(self.current_time, addr_v))

        self.address = list(reversed(addr_v))

        # Needed signals
        self.chip_enable = 1
        self.read = 1

        self.acc_en = 1
        self.acc_en_inv = 0

        self.duty_cycle = self.read_duty_cycle
        self.period = self.read_period

        self.update_output()

    def write_address(self, addr, data_v, mask_v):
        """Write data to an address. Data can be integer or binary vector. Address is binary vector"""

        addr_v = self.convert_address(addr)

        self.command_comments.append("* [{: >20}] write {}, {}\n".format(self.current_time, addr_v, data_v))

        self.mask = list(reversed(mask_v))
        self.address = list(reversed(addr_v))
        self.data = list(reversed(data_v))

        # Needed signals
        self.chip_enable = 1
        self.read = 0
        self.acc_en = 0
        self.acc_en_inv = 1

        self.period = self.write_period
        self.duty_cycle = self.write_duty_cycle

        self.update_output()

    def setup_write_measurements(self, address_int):
        """new_val is MSB first"""
        bank_index, _, row, col_index = self.probe.decode_address(address_int)
        self.sf.write("* -- Write : [{0}, {1}, {2}, {3}, {4}, {5}, {6}]\n".format(
            address_int, row, col_index, bank_index, self.current_time, self.write_period,
            self.write_duty_cycle))

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
            targ_val = 0.5 * self.vdd_voltage
            targ_dir = "CROSS"

            meas_name = "STATE_DELAY_a{}_c{}_t{}".format(address_int, i, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name=self.clk_buf_probe, trig_val=0.5 * self.vdd_voltage, trig_dir="FALL",
                                     trig_td=time + self.duty_cycle * self.period,
                                     targ_name=state_labels[i], targ_val=targ_val, targ_dir=targ_dir,
                                     targ_td=time + self.duty_cycle * self.period)

    def setup_decoder_delays(self):
        time_suffix = "{:.2g}".format(self.current_time).replace('.', '_')
        for address_int, in_nets in self.probe.decoder_inputs_probes.items():
            for i in range(len(in_nets)):
                meas_name = "decoder_in{}_{}_t{}".format(address_int, i, time_suffix)
                self.stim.gen_meas_delay(meas_name=meas_name,
                                         trig_name=self.clk_buf_probe, trig_val=0.5 * self.vdd_voltage, trig_dir="RISE",
                                         trig_td=self.current_time,
                                         targ_name=in_nets[i], targ_val=0.5 * self.vdd_voltage, targ_dir="CROSS",
                                         targ_td=self.current_time)
        if OPTS.push:
            trig_dir = "FALL"
        else:
            trig_dir = "RISE"
        for address_int, decoder_label in self.decoder_probes.items():
            time_suffix = "{:.2g}".format(self.current_time).replace('.', '_')
            meas_name = "decoder_a{}_t{}".format(address_int, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name=self.clk_buf_probe, trig_val=0.5 * self.vdd_voltage, trig_dir=trig_dir,
                                     trig_td=self.current_time,
                                     targ_name=decoder_label, targ_val=0.5 * self.vdd_voltage, targ_dir="CROSS",
                                     targ_td=self.current_time)

    def setup_precharge_measurement(self):
        time = self.current_time
        # power measurement
        time_suffix = "{:.2g}".format(time).replace('.', '_')
        trig_val = 0.1 * self.vdd_voltage
        targ_val = 0.9 * self.vdd_voltage
        for i in range(self.word_size):
            for bitline in ["bl", "br"]:
                if bitline == "br":
                    probe = self.bitline_probes[i]
                else:
                    probe = self.br_probes[i]
                meas_name = "PRECHARGE_DELAY_{}_c{}_t{}".format(bitline, i, time_suffix)
                self.stim.gen_meas_delay(meas_name=meas_name,
                                         trig_name=self.clk_buf_probe, trig_val=trig_val, trig_dir="RISE",
                                         trig_td=time,
                                         targ_name=probe, targ_val=targ_val, targ_dir="RISE",
                                         targ_td=time)

    def setup_read_measurements(self, address_int):
        """new_val is MSB first"""

        bank_index, _, row, col_index = self.probe.decode_address(address_int)
        self.sf.write("* -- Read : [{0}, {1}, {2}, {3}, {4}, {5}, {6}]\n".format(
            address_int, row, col_index, bank_index, self.current_time, self.read_period,
            self.read_duty_cycle))

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
        self.stim.instantiate_sram(sram=self.sram)

        self.stim.inst_accesstx(self.word_size)

    def write_ic(self, ic, col_node, col_voltage):
        if self.is_cmos:
            ic.write(".ic V({})={} \n".format(col_node, col_voltage))
        else:
            phi = 0.1 * OPTS.llg_prescale
            theta = np.arccos(col_voltage) * OPTS.llg_prescale

            phi_node = col_node.replace(".state", ".I0.phi")
            theta_node = col_node.replace(".state", ".I0.theta")

            ic.write(".ic V({})={} \n".format(phi_node, phi))
            ic.write(".ic V({})={} \n".format(theta_node, theta))
