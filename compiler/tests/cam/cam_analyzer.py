import re

import numpy as np

from tests.sim_analyzer_test import SimAnalyzerTest, print_max_delay


class CamAnalyzer(SimAnalyzerTest):
    def setUp(self):
        super().setUp()
        self.update_global_opts()
        self.read_settling_time = self.search_settling_time = 250e-12
        self.write_settling_time = 200e-12

    def analyze_energy(self):
        self.set_energy_vdd()
        op_energies, self.read_period = self.analyze_energy_events("SEARCH")
        op_energies, self.write_period = self.analyze_energy_events("WRITE")

    def print_sense_en_delay(self):
        delay = self.voltage_probe_delay("control_buffers", "search_sense_en", self.probe_bank,
                                         self.probe_row, edge=self.RISING_EDGE)
        print_max_delay("Sense EN", delay)

    def print_sense_bl_br_delay(self):
        self.print_ml_delay()

    def print_ml_delay(self):
        ml_delay = self.voltage_probe_delay("search_sense_amps", "vin",
                                            self.probe_bank, self.probe_row)
        print_max_delay("ML fall", ml_delay)

    def print_sense_out_delay(self):
        delay = self.voltage_probe_delay("search_sense_amps", "dout", self.probe_bank,
                                         self.probe_row)
        print_max_delay("Sense out", delay)

    def load_events(self):
        opts = self.cmd_line_opts
        self.all_search_events = (self.analyzer.load_events("Search")
                                  if not opts.skip_read_check else [])
        self.all_read_events = self.all_search_events
        self.all_write_events = (self.analyzer.load_events("Write")
                                 if not opts.skip_write_check else [])

    @staticmethod
    def print_search_error(search_data, address_data, bit_matches):
        from characterizer.simulation.sim_analyzer import print_vectors
        bits = list(reversed(range(len(search_data))))
        search_data = [str(search_data[i]) if not bit_matches[i] else '*'
                       for i in range(len(bit_matches))]
        address_data = [str(address_data[i]) if not bit_matches[i] else '*'
                        for i in range(len(bit_matches))]

        print_vectors(["", "addr_data", "search_data"],
                      [bits, address_data, search_data])

    def verify_search_event(self, event, negate=False):
        search_time, search_address, search_period, search_duty = event[:4]

        input_time = search_time + search_duty * search_period
        address_data = self.analyzer.get_address_data(search_address, input_time)
        search_data = self.analyzer.get_data_in(input_time)
        search_mask = self.analyzer.get_mask(input_time)

        bit_matches = [True] * self.word_size
        for bit in range(self.word_size):
            bit_match = address_data[bit] == search_data[bit]
            if search_mask[bit]:
                if (bit_match and negate) or not (bit_match or negate):
                    bit_matches[bit] = False
        out_time = search_time + search_period + self.search_settling_time
        bank = event[-1]
        row = event[-3]
        search_net = self.voltage_probes["dout"][str(bank)][str(row)]

        search_out = self.sim_data.get_binary(search_net, out_time)[0]

        match = np.all(bit_matches)
        correct = search_out == match
        if not correct:
            self.print_search_error(search_data, address_data, bit_matches)

        return correct

    def eval_read_delays(self, max_search_event):
        from characterizer.simulation import sim_analyzer
        dout_dict = next(iter(self.voltage_probes["dout"].values()))
        search_net = next(iter(dout_dict.values()))

        pattern = re.sub(r"\[[0-9]+\]", "[{}]", search_net)

        sim_analyzer.DATA_OUT_PATTERN = pattern
        return super().eval_read_delays(max_search_event)

    def check_read_correctness(self):
        negate_read = self.get_read_negation()

        max_search_event = None

        for event in self.all_search_events:
            print(f"Search {event[1]} at time: {event[0] * 1e9:.4g} n")
            correct = self.verify_search_event(event, negate_read)
            if not correct:
                max_search_event = event
        return max_search_event

    def plot_read_signals(self):
        self.plot_sig(self.get_plot_probe("control_buffers", "sense_en"),
                      label="sense_en")

        self.plot_sig(self.get_plot_probe("search_sense_amps", "vin", bit=self.probe_row),
                      label=f"ml[{self.probe_row}]")
        self.plot_sig(self.get_plot_probe("search_sense_amps", "dout", bit=self.probe_row),
                      label=f"search_out[{self.probe_row}]")
