#!/usr/bin/env python3
"""
Analyze bitline compute simulation for correctness
"""
import itertools
import re

import numpy as np

from test_base import TestBase
from bl_simulator import BlSimulator
from sim_analyzer_test import SimAnalyzerTest, print_max_delay


class AnalyzeBlSimulation(BlSimulator, SimAnalyzerTest, TestBase):

    def setUp(self):
        super().setUp()
        self.update_global_opts()

    def initialize(self):
        super().initialize()
        if self.baseline:
            self.read_settling_time = 120e-12
        elif self.one_t_one_s:
            self.analyzer.address_data_threshold = 0
            self.read_settling_time = 0e-12
        else:
            self.read_settling_time = -50e-12
        self.write_settling_time = 150e-12
        self.bitline_settling_time = 100e-12

    def create_analyzer(self):
        from characterizer.simulation.sim_analyzer import SimAnalyzer
        test_self = self

        class BlAnalyzer(SimAnalyzer):
            def get_address_data(self, address, time, threshold=None):
                threshold = threshold or getattr(self, "address_data_threshold", None)
                address_data = super().get_address_data(address, time, threshold)
                if test_self.one_t_one_s:
                    return [int(not x) for x in address_data]
                return address_data

        self.analyzer = BlAnalyzer(self.temp_folder)

    def plot_internal_sense_amp(self):
        if self.baseline:
            return super().plot_internal_sense_amp()
        for net in ["and", "nor"]:
            sig_name = self.analyzer.get_probe(net, bank=None, net=None,
                                               bit=self.probe_control_bit)
            self.plot_sig(sig_name, label=net)

        if self.latched:
            # internal_nets = ["and", "nor", "int1", "int2"]
            internal_nets = ["vref", "and_int", "nor_int"]
        else:
            internal_nets = ["int1", "int2"]
        for net in internal_nets:
            self.plot_sig(self.get_plot_probe("sense_amp_array", net),
                          label=net)

    def print_sense_out_delay(self):
        delay = self.voltage_probe_delay("sense_amp_array", "and", self.probe_bank,
                                         self.probe_control_bit)
        print_max_delay("Sense out", delay)

    def load_events(self):
        super().load_events()
        if self.baseline:
            return
            # filter read events in which s_and is selected
        actual_read_events = []
        for event in self.all_read_events:
            read_time = event[0]
            sel_and = self.sim_data.get_binary("s_and", read_time)[0]
            en_1 = self.sim_data.get_binary("en_1", read_time)[0]
            if sel_and and not en_1:
                self.read_duty_cycle = event[3]
                self.read_period = event[2]
                actual_read_events.append(event)
        self.all_read_events = actual_read_events

        actual_write_events = []
        for event in self.all_write_events:
            s_data = self.sim_data.get_binary("s_data", event[0])[0]
            if s_data:
                actual_write_events.append(event)
        self.all_write_events = actual_write_events

        self.all_blc_events = self.analyzer.load_events("BLC")
        self.all_src_events = self.analyzer.load_events("src")
        self.all_c_val_events = self.analyzer.load_events("c_val")

    def analyze_write_events(self):
        res = super().analyze_write_events()
        self.analyze_blc_events()
        self.analyze_c_val_events()
        return res

    def evaluate_write_critical_path(self, max_write_event, max_write_bit_delays):
        super().evaluate_write_critical_path(max_write_event, max_write_bit_delays)
        self.evaluate_blc_critical_path()

    def get_bus_as_int(self, pattern, bus_size, time):
        bus_binary = self.sim_data.get_bus_binary(pattern, bus_size, time)
        return int("".join(map(str, bus_binary)), 2)

    def analyze_blc_events(self):

        self.addr_size = int(np.log2(self.cmd_line_opts.num_words))
        self.all_blc_events = list(map(list, self.all_blc_events))
        print("----------------Bitline Compute---------------")

        for event in self.all_blc_events:
            event_time, _, period, duty_cycle = event[:4]

            blc_res = self.verify_bl_compute(event)
            blc_end, initial_d1, initial_d2, expected_and, expected_nor = blc_res
            self.verify_sum(event, blc_end, initial_d1, initial_d2,
                            expected_and, expected_nor)

    def verify_bl_compute(self, event):
        from characterizer.simulation.sim_analyzer import debug_error

        event_time, _, period, duty_cycle = event[:4]

        cycle_end = event_time + (1 + duty_cycle) * period

        addr_1 = self.get_bus_as_int("A[{}]", self.addr_size, event_time)
        event[1] = addr_1
        addr_2 = self.get_bus_as_int("A_1[{}]", self.addr_size, event_time)

        print(f"Bitline compute {addr_1} and {addr_2} at time {event_time * 1e9:.3g} ns")

        initial_d1 = self.analyzer.get_address_data(addr_1, event_time)
        initial_d2 = self.analyzer.get_address_data(addr_2, event_time)

        # verify and and nor calculated correctly
        expected_and = [d1 & d2 for d1, d2 in zip(initial_d1, initial_d2)]
        expected_nor = [int(not (d1 | d2)) for d1, d2 in zip(initial_d1, initial_d2)]

        and_probes = self.voltage_probes["and"]
        actual_and = self.analyzer.get_msb_first_binary(and_probes, cycle_end)
        nor_probes = self.voltage_probes["nor"]
        actual_nor = self.analyzer.get_msb_first_binary(nor_probes, cycle_end)

        debug_error(f"AND failure: At time {event_time * 1e9:.3g} n ",
                    expected_and, actual_and)
        debug_error(f"NOR failure: At time {event_time * 1e9:.3g} n ",
                    expected_nor, actual_nor)

        # verify data was not over-written
        new_d1 = self.analyzer.get_address_data(addr_1, cycle_end)
        debug_error(f"Address {addr_1} overwritten", initial_d1, new_d1)
        new_d2 = self.analyzer.get_address_data(addr_2, cycle_end)
        debug_error(f"Address {addr_2} overwritten", initial_d2, new_d2)

        return cycle_end, initial_d1, initial_d2, expected_and, expected_nor

    def verify_sum(self, event, blc_end, initial_d1, initial_d2,
                   expected_and, expected_nor):
        from characterizer.simulation.sim_analyzer import debug_error
        from modules.bitline_compute.bitline_spice_characterizer import alu_sum

        word_size = self.cmd_line_opts.alu_word_size
        num_words = int(self.cmd_line_opts.num_cols / word_size)

        def get_word(index, vec):
            index = num_words - index - 1
            return vec[index * word_size:(1 + index) * word_size]

        get_msb_binary = self.analyzer.get_msb_first_binary
        period = event[2]
        # verify sum and carry

        compute_time = event[0]
        event_duty = event[3]
        sum_end = compute_time + (1 + event_duty) * period + self.bitline_settling_time
        write_end = blc_end + period

        blc_bus_out = get_msb_binary(self.voltage_probes["dout"], sum_end)
        write_address = self.get_bus_as_int("A[{}]", self.addr_size, blc_end)
        actual_mask_bar = get_msb_binary(self.voltage_probes["bank_mask_bar"], sum_end)

        if self.serial:
            # cin = get_msb_binary(self.voltage_probes["cin"], blc_end)
            probes = self.voltage_probes["alu"]["cin"]
            cin = get_msb_binary(probes, blc_end)
            cout = get_msb_binary(self.voltage_probes["cout"], sum_end)
        else:
            probes = self.voltage_probes["cin"]
            cin = get_msb_binary(probes, blc_end)
            cout = get_msb_binary(self.voltage_probes["cout"], sum_end)

        previous_data = self.analyzer.get_address_data(write_address, compute_time)
        actual_data = self.analyzer.get_address_data(write_address, write_end)

        expected_data_in = self.analyzer.get_data_in(sum_end)

        expectations = [None, expected_and, expected_nor, expected_data_in]

        sig_names = ["s_sum", "s_and", "s_nor", "s_data"]
        expected_result = None
        for j in range(len(sig_names)):
            selected = self.sim_data.get_binary(sig_names[j], sum_end)[0]
            if selected:
                expected_result = expectations[j]
                break

        bank_sel = not self.sim_data.get_binary("Csb", sum_end)[0]

        expected_sums = list(reversed(alu_sum(initial_d1, initial_d2, cin, word_size)))

        for word in range(num_words):
            expected_sum, expected_carry = expected_sums[word]

            actual_sum = get_word(word, blc_bus_out)
            if expected_result is None:
                expected_write_back = expected_sum
            else:
                expected_write_back = get_word(word, expected_result)

            is_correct = debug_error(f"Incorrect sum (word {word}) "
                                     f"at time {compute_time * 1e9:.3g} n",
                                     expected_write_back, actual_sum)
            if is_correct:
                if self.serial:
                    actual_carry = get_word(word, cout)
                else:
                    actual_carry = [list(reversed(cout))[word]]
                debug_error(f"Incorrect carry (word {word}) at time"
                            f" {compute_time * 1e9:.3g}",
                            expected_carry, actual_carry)

            if bank_sel:
                expected_data = [get_word(word, previous_data)[i]
                                 if get_word(word, actual_mask_bar)[i]
                                 else expected_write_back[i]
                                 for i in range(word_size)]
                written_data = get_word(word, actual_data)
                debug_error(f"Write-back to {write_address} (word {word}) unsuccessful "
                            f"at time {compute_time * 1e9:.3g} ",
                            expected_data, written_data)

    def analyze_c_val_events(self):
        if not self.serial:
            return
        from characterizer.simulation.sim_analyzer import debug_error
        print("TODO: Verify c_val")
        return

        for event in self.all_c_val_events:
            event_time, _, period, duty_cycle = event[:4]

            c_val = self.analyzer.get_msb_first_binary(self.voltage_probes["c_val"],
                                                       event_time + duty_cycle * period)
            cin = self.analyzer.get_msb_first_binary(self.voltage_probes["cin"],
                                                     event_time + period)
            debug_error("c_val initialization failure at time {:.3g}".format(event_time),
                        c_val, cin)

    def evaluate_bus_delay(self, probe_dict, start_time, end_time,
                           clk_bar=True, bus_edge=None):
        delay_func = self.analyzer.clk_bar_to_bus_delay if clk_bar else \
            self.analyzer.clk_to_bus_delay
        sorted_keys = list(sorted(probe_dict.keys(), key=int, reverse=True))
        delays = []
        for key in sorted_keys:
            delays.append(delay_func(probe_dict[key], start_time, end_time,
                                     bus_edge=bus_edge))
        return delays, sorted_keys

    def evaluate_blc_critical_path(self):

        def get_max_delay(delays, keys):
            arg_max = np.argmax(delays)
            return delays[arg_max], keys[arg_max]

        def format_max_delay(probes, event_name, event_time_, start_time, end_time):
            bus_delays, sorted_keys = self.evaluate_bus_delay(probes,
                                                              start_time, end_time)

            max_delay, max_col = get_max_delay(bus_delays, sorted_keys)
            print(f"max clk_bar to {event_name} delay at {event_time_ * 1e9:.3g}n "
                  f"= {max_delay / 1e-12:4.4g}p at"
                  f" col {max_col}")

        # temporary restrict max delay to less than a clock cycle
        delay_factor = 1  # should be 1

        for event in self.all_blc_events:
            event_time, _, period, duty_cycle = event[:4]

            clk_time = event_time + duty_cycle * period

            and_end_time = event_time + period
            format_max_delay(self.voltage_probes["and"], "AND", event_time,
                             clk_time, and_end_time)

            format_max_delay(self.voltage_probes["nor"], "NOR", event_time,
                             clk_time, and_end_time)

            sum_end_time = event_time + (delay_factor + duty_cycle) * period

            format_max_delay(self.voltage_probes["dout"], "SUM", event_time,
                             clk_time, sum_end_time)
            print()

        self.analyze_delay_sim_energies()

    def analyze_delay_sim_energies(self):
        if not self.all_blc_events:
            return
        energy_func = self.analyzer.measure_energy

        period = self.all_blc_events[0][2]

        matches = re.findall(r"^\*\s+\[([0-9+\.\ ]+)\]\s+([a-zA-Z_\.]+)",
                             self.analyzer.stim_str, re.MULTILINE)
        groups = {key: list(values) for key, values in
                  itertools.groupby(matches, key=lambda x: x[1])}
        for event_name in sorted(groups.keys()):
            event_times = [1e-9 * float(x[0]) for x in groups[event_name]]
            event_times = list(sorted(event_times))
            event_energies = []
            for event_time in event_times:
                event_end = event_time + period
                op_energy = energy_func([event_time, event_end])
                event_energies.append(op_energy)
            mean_energy = 1e12 * np.mean(event_energies)
            print(f"Mean {event_name} energy = {mean_energy:.3g} pJ")

    def run_plots(self):
        if self.cmd_line_opts.plot == "blc":
            max_read_event_old = self.max_read_event
            max_read_event = (self.get_analysis_events(self.all_blc_events, None)
                              or self.all_blc_events[0])
            max_read_event = [x for x in max_read_event]
            # cover both blc and write back
            max_read_event[2] *= 2

            self.max_read_event = max_read_event or self.all_blc_events[0]
            self.cmd_line_opts.plot = "read"
            super().run_plots()
            self.cmd_line_opts.plot = "blc"
            self.max_read_event = max_read_event_old
        else:
            super().run_plots()

    def plot_write_signals(self):
        super().plot_write_signals()
        if self.one_t_one_s:
            self.plot_mram_current()
            # self.probe_address += 1
            # self.plot_mram_current()
            # self.probe_address -= 1

    def plot_bitlines(self):
        if not self.one_t_one_s or self.cmd_line_opts.plot == "read":
            return super().plot_bitlines()
        address = self.probe_address
        if address % 2 == 0:
            bl, br = ["bl", "blb"]
        else:
            bl, br = ["br", "brb"]

        self.plot_sig(self.get_plot_probe(bl, None, self.probe_col),
                      label=f"{bl}[{self.probe_col}]")
        self.plot_sig(self.get_plot_probe(br, None, self.probe_col),
                      label=f"{br}[{self.probe_col}]")

    def get_wl_name(self):
        if self.one_t_one_s and self.cmd_line_opts.plot == "write":
            return "wwl"
        return "wl"

    def test_analysis(self):
        self.analyze()


if __name__ == "__main__":
    AnalyzeBlSimulation.parse_options()
    AnalyzeBlSimulation.run_tests(__name__)
