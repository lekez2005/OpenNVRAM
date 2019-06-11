import itertools
import os
from importlib import reload

import characterizer
from characterizer.sequential_delay import SequentialDelay
from globals import OPTS
from sf_cam_dut import SfCamDut
from sf_cam_probe import SfCamProbe


class SfCamDelay(SequentialDelay):

    ramp_time = period = 0
    write_period = search_period = 0
    search_duty_cycle = write_duty_cycle = 0
    saved_nodes = []
    ml_precharge_addresses = None  # for search delays

    sf = None

    def __init__(self, sram, spfile, corner, initialize=False):
        super().__init__(sram, spfile, corner, initialize=initialize)

        # set up for write
        self.search = self.prev_search = 0
        self.mask = self.prev_mask = [1] * OPTS.word_size
        for i in range(self.word_size):
            self.bus_sigs.append("mask[{}]".format(i))

        self.control_sigs = ["search"]

    def write_delay_stimulus(self):
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
        self.sf.write("* Delay stimulus for search period = {0}n, write period = {1} load={2}fF slew={3}ns\n\n".format(
            self.search_period, self.write_period, self.load, self.slew))

        self.stim = SfCamDut(self.sf, self.corner)

        self.stim.write_include(self.trim_sp_file)

        self.write_generic_stimulus()

        self.initialize_output()

        self.generate_steps()

        for node in self.saved_nodes:
            self.sf.write(".plot V({0}) \n".format(node))

        self.finalize_output()

        # run until the end of the cycle time
        self.stim.write_control(self.current_time + self.period)

        self.sf.close()

    def generate_steps(self):
        probe = SfCamProbe(self.sram, self.sp_file)
        self.ml_precharge_addresses = self.probe_matchlines(probe, self.sram)

        zero_address = 0
        max_address = self.sram.num_words - 1

        probe.probe_address(zero_address)
        probe.probe_address(max_address)

        zero_one_mix = list(itertools.chain.from_iterable(zip([1]*self.word_size, [0]*self.word_size)))
        one_zero_data = zero_one_mix[:self.word_size]

        one_mismatch = list(one_zero_data)
        one_mismatch[0] = 0

        one_zero_data = [1] * self.word_size
        one_mismatch = [1] * self.word_size

        mask = [1] * self.word_size
        self.write_masked_data(self.convert_address(zero_address), self.invert_vec(one_zero_data), mask,
                               "reset address {}".format(zero_address))
        self.write_masked_data(self.convert_address(max_address), self.invert_vec(one_mismatch), mask,
                               "reset address {}".format(max_address))

        self.write_masked_data(self.convert_address(zero_address), one_zero_data, mask,
                               "write {} to address {}".format(one_zero_data, zero_address))
        self.setup_write_measurements(zero_address, one_zero_data,
                                      probe.decoder_probes[zero_address], probe.state_probes[zero_address])

        self.write_masked_data(self.convert_address(max_address), one_mismatch, mask,
                               "write {} to address {}".format(one_mismatch, max_address))
        self.setup_write_measurements(max_address, one_mismatch,
                                      probe.decoder_probes[max_address], probe.state_probes[max_address])

        self.search_data(one_zero_data, mask, "search data {}".format(one_zero_data))
        self.search_data(one_mismatch, mask, "search data {}".format(one_mismatch))

        self.measure_leakage()

        self.saved_nodes = sorted(set(probe.probe_labels))

    @staticmethod
    def invert_vec(data_vec):
        return [0 if x == 1 else 1 for x in data_vec]

    @staticmethod
    def probe_matchlines(probe, cam):
        addresses = []
        for i in range(cam.num_words):
            probe.probe_matchline(i)
            addresses.append({
                "addr_int": i,
                "label": probe.matchline_probes[i]
            })
        return addresses

    def update_output(self):
        # write mask
        for i in range(self.word_size):
            key = "mask[{}]".format(i)
            self.write_pwl(key, self.prev_mask[i], self.mask[i])
        self.prev_mask = self.mask
        super().update_output()

    def search_data(self, data, mask, comment=""):
        """data and mask are MSB first"""
        self.command_comments.append("* t = {} Search {}, Mask: {} {} \n".format(self.current_time, data,
                                                                                 mask, comment))
        self.data = list(reversed(self.convert_data(data)))
        self.mask = list(reversed(mask))
        self.search = 1

        self.duty_cycle = self.search_duty_cycle
        self.period = self.search_period

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
        time = self.current_time - self.period
        time_suffix = "{:.2g}".format(time).replace('.', '_')

        meas_name = "SEARCH_POWER_t{}".format(time_suffix)
        self.stim.gen_meas_power(meas_name=meas_name,
                                 t_initial=time - self.setup_time,
                                 t_final=time + self.period - self.setup_time)

        for addr in self.ml_precharge_addresses:
            self.stim.gen_meas_delay(meas_name="ML_rise_a{}_{}".format(addr["addr_int"], time_suffix),
                                     trig_name="clk", trig_val=0.9 * self.vdd_voltage, trig_dir="RISE",
                                     trig_td=time,
                                     targ_name=addr["label"], targ_val=0.9 * self.vdd_voltage, targ_dir="RISE",
                                     targ_td=time)
            self.stim.gen_meas_delay(meas_name="ML_fall_a{}_{}".format(addr["addr_int"], time_suffix),
                                     trig_name="clk", trig_val=0.1 * self.vdd_voltage, trig_dir="FALL",
                                     trig_td=time + self.duty_cycle*self.period,
                                     targ_name=addr["label"], targ_val=0.1 * self.vdd_voltage, targ_dir="FALL",
                                     targ_td=time + self.duty_cycle*self.period)

    def setup_write_measurements(self, address_int, new_val, decoder_label, state_labels):
        time = self.current_time - self.period
        # power measurement
        time_suffix = "{:.2g}".format(time).replace('.', '_')
        meas_name = "WRITE_POWER_t{}".format(time_suffix)
        self.stim.gen_meas_power(meas_name=meas_name,
                                 t_initial=time - self.setup_time,
                                 t_final=time + self.period - self.setup_time)
        # decoder delay
        self.stim.gen_meas_delay(meas_name="decoder_a{}_t{}".format(address_int, time_suffix),
                                 trig_name="clk", trig_val=0.9 * self.vdd_voltage, trig_dir="RISE",
                                 trig_td=time,
                                 targ_name=decoder_label, targ_val=0.9 * self.vdd_voltage, targ_dir="RISE",
                                 targ_td=time)
        for i in range(self.word_size):
            transition = "HL" if new_val[i] == 1 else "LH"
            targ_val = -0.05 if transition == "LH" else 0.05
            targ_dir = "FALL" if transition == "LH" else "RISE"
            meas_name = "STATE_DELAY_a{}_c{}_t{}".format(address_int, i, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name="clk", trig_val=0.1 * self.vdd_voltage, trig_dir="FALL",
                                     trig_td=time + 0.5*self.duty_cycle*self.period,
                                     targ_name=state_labels[i], targ_val=targ_val, targ_dir=targ_dir,
                                     targ_td=time + 0.5*self.duty_cycle*self.period)

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




