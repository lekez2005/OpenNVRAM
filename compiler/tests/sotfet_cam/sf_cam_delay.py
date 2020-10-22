import itertools
import json
import os
import re
from importlib import reload
from random import randint

import numpy as np

import characterizer
import verify
from characterizer.sequential_delay import SequentialDelay
from globals import OPTS
from sf_cam_dut import SfCamDut
from sf_cam_probe import SfCamProbe


class SfCamDelay(SequentialDelay):
    ramp_time = period = 0
    write_period = search_period = 0
    search_duty_cycle = write_duty_cycle = 0
    saved_nodes = []
    saved_currents = []
    ml_precharge_addresses = None  # for search delays

    clk_probe = "clk"

    sf = None

    def __init__(self, sram, spfile, corner, initialize=False):
        super().__init__(sram, spfile, corner, initialize=initialize)

        self.cmos = OPTS.bitcell == "cam_bitcell"

        self.separate_vdd = OPTS.separate_vdd if hasattr(OPTS, 'separate_vdd') else False

        # set up for search
        self.search = self.prev_search = 1
        self.mask = self.prev_mask = [1] * OPTS.word_size
        self.bank_sel = self.prev_bank_sel = 1
        for i in range(self.word_size):
            self.bus_sigs.append("mask[{}]".format(i))

        self.control_sigs = ["search", "bank_sel"]

    def initialize_sim_file(self):
        """ Override super class method to use internal logic for pwl voltages and measurement setup
        Assumes set_stimulus_params has been called to define the addresses and nodes
         Creates a stimulus file for simulations to probe a bitcell at a given clock period.
        Address and bit were previously set with set_stimulus_params().
        """

        reload(characterizer)

        # creates and opens stimulus file for writing
        self.current_time = 0
        temp_stim = os.path.join(OPTS.openram_temp, "stim.sp")
        self.sf = open(temp_stim, "w")
        self.sf.write("{} \n".format(self.sram))
        if OPTS.spice_name == "spectre":
            self.sf.write("simulator lang=spice\n")
        self.sf.write("* Delay stimulus for search period = {0}n, write period = {1}n load={2}fF slew={3}ns\n\n".format(
            self.search_period, self.write_period, self.load, self.slew))

        self.sf.write("* search_duty = {0}n, write_duty = {1}n".format(self.search_duty_cycle, self.write_duty_cycle))
        self.sf.write("* Area = {0:.0f}um2".format(self.sram.width * self.sram.height))

        self.stim = SfCamDut(self.sf, self.corner)

        self.write_generic_stimulus()

        self.initialize_output()

    def finalize_sim_file(self):

        self.saved_nodes.append(self.clk_probe)

        for node in set(self.saved_nodes):
            self.sf.write(".probe V({0}) \n".format(node))

        self.sf.write("simulator lang=spectre \n")
        for node in self.saved_currents:
            self.sf.write("save {0} \n".format(node))
        self.sf.write("simulator lang=spice \n")

        self.finalize_output()

        self.stim.write_include(self.trim_sp_file)
        self.stim.replace_sotfet_cells(self.sram)

        # run until the end of the cycle time
        self.stim.write_control(self.current_time + 2 * self.period)

        self.sf.close()

        # save state probes
        state_probe_file = os.path.join(OPTS.openram_temp, "state_probes.json")
        with open(state_probe_file, "w") as f:
            json.dump(self.probe.state_probes, f, indent=4, sort_keys=True)

    def probe_addresses(self, addresses):
        self.probe = probe = SfCamProbe(self.sram, OPTS.pex_spice)
        self.probe_matchlines(probe, self.sram)

        probe.probe_bitlines(0)
        probe.probe_misc_bank(0)

        for address in addresses:
            probe.probe_address(address)

        self.sf.write("* saved addresses = {} \n".format(", ".join(map(str, addresses))))

        if not OPTS.energy:
            self.run_drc_lvs_pex()

        probe.extract_probes()

        self.clk_probe = probe.clk_probe

        self.ml_precharge_addresses = probe.get_matchline_probes()

        return probe

    def generate_energy_steps(self):
        num_sims = OPTS.energy
        mask = [1] * self.sram.word_size

        if self.word_size == 36:  # CAPE architecture
            search_mask = [0] * (self.word_size - 4) + [1, 1, 1, 1]
        else:
            search_mask = [1] * self.word_size

        ops = ["search", "write"]
        for i in range(num_sims):

            data = [randint(0, 1) for x in range(self.sram.word_size)]

            op = ops[randint(0, 1)]

            if op == "search":
                self.search_data(data, search_mask)
            else:
                address = randint(0, self.sram.num_words - 1)
                self.write_masked_data(self.convert_address(address), data, mask)
            self.sf.write("* -- {}: t = {:.5g} period = {}\n".
                          format(op.upper(), self.current_time - self.period,
                                 self.period))
        self.current_time += 2 * self.period  # to cool off from previous event
        self.period = max(self.search_period, self.write_period)
        self.bank_sel = 0

        self.update_output()

        leakage_cycles = 10
        start_time = self.current_time
        end_time = start_time + leakage_cycles * self.search_period
        self.current_time = end_time

        self.sf.write("* -- LEAKAGE start = {:.5g} end = {:.5g}\n".format(start_time,
                                                                          self.current_time))

        self.sf.write("* --clk_buf_probe={}--\n".format(self.probe.clk_probe))

    def generate_steps(self):

        zero_address = 0
        max_address = self.sram.num_words - 1
        dummy_address = 1
        probe = self.probe_addresses([zero_address, max_address, dummy_address])

        data = [1] * self.word_size
        data_mismatch = [1] * (self.word_size - 1) + [0]

        self.initialize_sram(probe, {
            zero_address: data,
            max_address: data_mismatch
        })

        zero_one_mix = list(itertools.chain.from_iterable(zip([1] * self.word_size, [0] * self.word_size)))
        one_zero_data = zero_one_mix[:self.word_size]

        one_mismatch = list(one_zero_data)
        one_mismatch[-1] = 1

        # one_zero_data = [1] * self.word_size
        # one_mismatch = [1] * self.word_size

        mask = [1] * self.word_size
        zero_mask = [0] * self.word_size

        if self.word_size == 36:  # CAPE architecture
            search_mask = [0] * (self.word_size - 4) + [1, 1, 1, 1]
        else:
            search_mask = [1] * self.word_size

        self.search_data(data, search_mask, "".format(data))
        self.search_data(data_mismatch, search_mask, "".format(data_mismatch))

        self.write_masked_data(self.convert_address(zero_address), self.invert_vec(one_zero_data), mask,
                               "reset address".format(zero_address))
        self.write_masked_data(self.convert_address(max_address), self.invert_vec(one_mismatch), mask,
                               "reset address".format(max_address))

        self.write_masked_data(self.convert_address(zero_address), one_zero_data, mask,
                               " address {}".format(zero_address))
        self.setup_write_measurements(zero_address, one_zero_data,
                                      probe.decoder_probes[zero_address], probe.state_probes[zero_address])

        self.write_masked_data(self.convert_address(max_address), one_mismatch, mask,
                               " address {}".format(one_mismatch, max_address))
        self.setup_write_measurements(max_address, one_mismatch,
                                      probe.decoder_probes[max_address], probe.state_probes[max_address])

        # let two periods pass for sotfets before searching
        if not self.cmos:
            self.write_masked_data(self.convert_address(dummy_address), one_mismatch, zero_mask)
            self.write_masked_data(self.convert_address(dummy_address), one_mismatch, zero_mask)

        self.search_data(one_zero_data, search_mask, "".format(one_zero_data))
        self.search_data(one_mismatch, search_mask, "".format(one_mismatch))

        self.saved_nodes = sorted(probe.saved_nodes)

    @staticmethod
    def invert_vec(data_vec):
        return [0 if x == 1 else 1 for x in data_vec]

    @staticmethod
    def probe_matchlines(probe, cam):
        for i in range(cam.num_words):
            probe.probe_matchline(i)

    def write_ic(self, ic, col_node, col_voltage):
        if self.cmos:
            ic.write("ic {}={} \n".format(col_node, col_voltage))
        else:
            phi = 0.1 * OPTS.llg_prescale

            phi1_node = col_node.replace(".mz1", ".I8.phi")
            phi2_node = col_node.replace(".mz1", ".I9.phi")

            theta1_node = col_node.replace(".mz1", ".I8.theta")
            theta2_node = col_node.replace(".mz1", ".I9.theta")

            nodes = [phi1_node, phi2_node, theta1_node, theta2_node]
            values = [phi, phi, np.arccos(col_voltage), np.arccos(-col_voltage)]

            for i in range(4):
                ic.write("ic {}={} \n".format(nodes[i], values[i] * OPTS.llg_prescale))

    def binary_to_voltage(self, x):
        if self.cmos:
            return x * self.vdd_voltage
        else:
            return 0.995 * ((x * 2) - 1)  # close to +-1 but not exactly equal for convergence reasons

    def update_output(self, increment_time=True):
        # write mask
        for i in range(self.word_size):
            key = "mask[{}]".format(i)
            self.write_pwl(key, self.prev_mask[i], self.mask[i])
        self.prev_mask = self.mask
        super().update_output(increment_time)

    def search_data(self, data, mask, comment=""):
        """data and mask are MSB first"""
        self.command_comments.append("* t = {} Search {}, Mask: {} {} \n".format(self.current_time, data,
                                                                                 mask, comment))
        # search for inverse if PCAM
        if not self.cmos and not OPTS.series:
            data = self.invert_vec(data)
        self.data = list(reversed(self.convert_data(data)))
        self.mask = list(reversed(mask))
        self.search = 1

        self.duty_cycle = self.search_duty_cycle
        self.period = self.search_period

        if not OPTS.energy:
            self.setup_search_measurements()
        self.update_output()

    def write_masked_data(self, address_vec, data_vec, mask_vec, comment=""):
        """Write data to an address. Data can be integer or binary vector. Address is binary vector"""
        self.command_comments.append("* t = {} Write {} to {} {} \n".format(self.current_time, data_vec,
                                                                            address_vec, comment))
        self.mask = list(reversed(mask_vec))
        self.address = list(reversed(address_vec))
        self.data = list(reversed(data_vec))

        self.search = 0

        self.duty_cycle = self.write_duty_cycle
        self.period = self.write_period

        self.update_output()

    def measure_leakage(self):
        self.write_pwl("search", self.prev_search, 1)
        self.write_pwl("clk", 0, 0)
        self.current_time += self.search_period  # settling time
        meas_name = "LEAKAGE_POWER"
        self.stim.gen_meas_power(meas_name=meas_name,
                                 t_initial=self.current_time,
                                 t_final=self.current_time + self.search_period)
        self.current_time += self.search_period

    def setup_search_measurements(self):
        time = self.current_time
        time_suffix = "{:.2g}".format(time).replace('.', '_')

        meas_name = "SEARCH_POWER_t{}".format(time_suffix)
        self.stim.gen_meas_power(meas_name=meas_name,
                                 t_initial=time - self.setup_time,
                                 t_final=time + self.period - self.setup_time)

        for addr in self.ml_precharge_addresses:
            self.stim.gen_meas_delay(meas_name="ML_rise_a{}_{}".format(addr["addr_int"], time_suffix),
                                     trig_name=self.clk_probe, trig_val=0.9 * self.vdd_voltage, trig_dir="RISE",
                                     trig_td=time,
                                     targ_name=addr["ml_label"], targ_val=0.9 * self.vdd_voltage, targ_dir="RISE",
                                     targ_td=time)
            self.stim.gen_meas_delay(meas_name="dout_fall_a{}_{}".format(addr["addr_int"], time_suffix),
                                     trig_name=self.clk_probe, trig_val=0.1 * self.vdd_voltage, trig_dir="FALL",
                                     trig_td=time + self.duty_cycle * self.period,
                                     targ_name=addr["dout_label"], targ_val=0.1 * self.vdd_voltage, targ_dir="FALL",
                                     targ_td=time + self.duty_cycle * self.period)

    def setup_write_measurements(self, address_int, new_val, decoder_label, state_labels):
        """new_val is MSB first"""
        time = self.current_time - self.period
        # power measurement
        time_suffix = "{:.2g}".format(time).replace('.', '_')
        meas_name = "WRITE_POWER_t{}".format(time_suffix)
        self.stim.gen_meas_power(meas_name=meas_name,
                                 t_initial=time - self.setup_time,
                                 t_final=time + self.period - self.setup_time)
        # decoder delay
        self.stim.gen_meas_delay(meas_name="decoder_a{}_t{}".format(address_int, time_suffix),
                                 trig_name=self.clk_probe, trig_val=0.9 * self.vdd_voltage, trig_dir="RISE",
                                 trig_td=time,
                                 targ_name=decoder_label, targ_val=0.9 * self.vdd_voltage, targ_dir="RISE",
                                 targ_td=time)
        new_val_reversed = list(reversed(new_val))
        for i in range(self.word_size):
            transition = "HL" if new_val_reversed[i] == 0 else "LH"
            if self.cmos:
                targ_val = 0.9 * self.vdd_voltage if transition == "LH" else 0.1 * self.vdd_voltage
                targ_dir = "RISE" if transition == "LH" else "FALL"
            else:
                # There are two rise times, time to rise cross threshold and time to relax
                # Measure time to cross threshold first
                meas_name = "STATE_CROSS_a{}_c{}_t{}".format(address_int, i, time_suffix)
                targ_val = -0.8 if transition == "LH" else 0.8
                targ_dir = "FALL" if transition == "LH" else "RISE"
                self.stim.gen_meas_delay(meas_name=meas_name,
                                         trig_name=self.clk_probe, trig_val=0.9 * self.vdd_voltage, trig_dir="RISE",
                                         trig_td=time,
                                         targ_name=state_labels[i], targ_val=0, targ_dir=targ_dir,
                                         targ_td=time)
            meas_name = "STATE_DELAY_a{}_c{}_t{}".format(address_int, i, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name=self.clk_probe, trig_val=0.1 * self.vdd_voltage, trig_dir="FALL",
                                     trig_td=time + self.duty_cycle * self.period,
                                     targ_name=state_labels[i], targ_val=targ_val, targ_dir=targ_dir,
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
