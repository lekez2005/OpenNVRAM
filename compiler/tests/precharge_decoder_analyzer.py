import os
from collections import defaultdict

import numpy as np

OP_FIRST_WRITE = "first-write"
OP_FIRST_READ = "first-read"
OP_DECODER_PRECHARGE = "decoder-precharge"


class PrechargeDecoderAnalyzer:
    decoder_threshold = float(os.getenv("DECODER_THRESHOLD", 0.95))
    precharge_threshold = float(os.getenv("PRECHARGE_THRESHOLD", 0.95))

    @classmethod
    def create_arg_parser(cls):
        parser = super(PrechargeDecoderAnalyzer, cls).create_arg_parser()
        parser.add_argument("--operation", choices=[OP_FIRST_WRITE, OP_FIRST_READ,
                                                    OP_DECODER_PRECHARGE])
        return parser

    def run_analysis(self):
        operation = self.cmd_line_opts.operation
        if operation == OP_DECODER_PRECHARGE:
            self.check_decoder_precharge()
        elif operation == OP_FIRST_WRITE:
            self.check_decoder_output()
        else:
            self.check_decoder_output()
            self.check_precharge()

    def get_edges(self, signal_name, threshold=0.5, rising=True):
        signal = self.sim_data.get_signal(signal_name)
        signal_binary = 1 * (signal > threshold * self.sim_data.vdd)
        signal_diff = np.diff(signal_binary).astype(int)
        if rising:
            indices = np.argwhere(signal_diff == 1)
        else:
            indices = np.argwhere(signal_diff == -1)
        indices += 1
        return self.sim_data.time[indices].squeeze(axis=1)

    def get_clk_edges(self, rising=True):
        decoder_clock = self.voltage_probes["clk"]["0"]
        return self.get_edges(decoder_clock, threshold=0.5, rising=rising)

    def trim_signal(self, signal, start_time, end_time):
        all_time = self.sim_data.time
        start_index = np.absolute(all_time - start_time).argmin()
        end_index = np.absolute(all_time - end_time).argmin()
        return signal[start_index:end_index + 1]

    def get_wordline_enable_probe(self, bank, net_name):
        control_probes = self.voltage_probes["control_buffers"][str(bank)]
        enable_row = str(max(map(int, control_probes[net_name].keys())))
        probe = control_probes[net_name][enable_row]
        return probe

    def get_wordline_enable_edges(self, bank=0, rising=True):
        edges = []
        for wl_enable in self.get_wordline_enable_names():
            probe = self.get_wordline_enable_probe(bank, wl_enable)
            edges.extend(self.get_edges(probe, rising=rising).tolist())
        return edges

    @staticmethod
    def get_wordline_enable_names():
        return ["wordline_en"]

    def check_decoder_output(self):
        clk_times = self.get_clk_edges(rising=True)[1:]
        wordline_edges = self.get_wordline_enable_edges()
        # get decoder edges
        decoder_edges = []
        for address, probe in self.voltage_probes["decoder"].items():
            # rises
            decoder_edges.extend(self.get_edges(probe, rising=True))

        errors = []

        for cycle_start, cycle_end in zip(clk_times[:-1], clk_times[1:]):
            for enable_edge in wordline_edges:
                if enable_edge < cycle_start or enable_edge > cycle_end:
                    continue
                for decoder_edge in decoder_edges:
                    if decoder_edge < cycle_start or decoder_edge > cycle_end:
                        continue
                    if decoder_edge > enable_edge:
                        errors.append(f"Enable edge = {enable_edge}, "
                                      f"Decoder edge = {decoder_edge}")
        if errors:
            assert False, "\n".join(errors)

    def get_precharge_bitline_names(self):
        return ["bl", "br"]

    def validate_precharge_signal(self, bitline_signal, signal_name,
                                  op_time, op_end, errors):
        max_value = max(bitline_signal)
        if max_value < self.precharge_threshold * self.sim_data.vdd:
            errors.append(f"{signal_name}, time: {op_time * 1e9:5.3f}n,"
                          f" max: {max_value:3.3g}")

    def get_precharge_end_time(self, cycle_start, cycle_end):
        return cycle_end

    def should_check_precharge(self, cycle_start):
        web = self.sim_data.get_signal("Web", from_t=cycle_start)[0]
        return web > 0.5 * self.sim_data.vdd

    def check_precharge(self):
        clk_times = self.get_clk_edges(rising=True)[1:]
        bitline_signals = []
        bitline_names = self.get_precharge_bitline_names()
        for bl_name in bitline_names:
            for bank in self.voltage_probes[bl_name]:
                for col, signal_name in self.voltage_probes[bl_name][bank].items():
                    signal = self.sim_data.get_signal(signal_name)
                    bitline_signals.append((signal_name, signal))

        errors = []
        for cycle_start, cycle_end in zip(clk_times[:-1], clk_times[1:]):
            if not self.should_check_precharge(cycle_start):
                continue
            # ensure all bitlines are at least precharge threshold
            precharge_end_time = self.get_precharge_end_time(cycle_start, cycle_end)
            for signal_name, bitline_signal in bitline_signals:
                bitline_signal = self.trim_signal(bitline_signal, cycle_start,
                                                  precharge_end_time)
                self.validate_precharge_signal(bitline_signal, signal_name, cycle_start,
                                               cycle_end, errors)

        if errors:
            assert False, "\n".join(errors)

    def check_decoder_precharge(self):
        from globals import OPTS
        self.load_events()
        decoder_delay = self.analyze_decoder()
        precharge_delay = self.analyze_precharge()
        print(f"---***{decoder_delay},{precharge_delay}---***")
        if OPTS.debug_level > 0:
            self.analyze_precharge_decoder(self.all_read_events +
                                           self.all_write_events)

    def analyze_decoder(self):
        clk_times = self.get_clk_edges(rising=True)
        decoder_delays = defaultdict(list)
        all_delays = []
        for address, probe in self.voltage_probes["decoder"].items():
            # rises
            address_delays = []
            rises = self.get_edges(probe, threshold=self.decoder_threshold, rising=True)
            falls = self.get_edges(probe, threshold=1 - self.decoder_threshold, rising=False)
            times = list(sorted(rises.tolist() + falls.tolist()))
            for time in times:
                for cycle_start, cycle_end in zip(clk_times[:-1], clk_times[1:]):
                    if cycle_start <= time <= cycle_end:
                        address_delays.append(time - cycle_start)
                        break
            decoder_delays[address] = address_delays
            all_delays.extend(address_delays)
        from globals import OPTS
        if OPTS.debug_level > 1:
            print(decoder_delays)
            print(all_delays)
        return max(all_delays)

    def analyze_precharge(self):
        from globals import OPTS
        clk_times = self.get_clk_edges(rising=True)

        errors = []
        delays = defaultdict(list)

        bitline_binary_signals = {}
        bitline_signals = {}
        bitline_names = ["bl"]
        for bl_name in bitline_names:
            for bank in self.voltage_probes[bl_name]:
                for col, signal_name in self.voltage_probes[bl_name][bank].items():
                    signal = self.sim_data.get_signal(signal_name)
                    key = f"{bank}_{bl_name}_{col}"
                    bitline_signals[key] = signal
                    _ = signal > self.precharge_threshold * self.sim_data.vdd
                    bitline_binary_signals[key] = _

        all_time = self.sim_data.time

        for i, (cycle_start, cycle_end) in enumerate(zip(clk_times[:-1], clk_times[1:])):
            # check if it's write operation
            web = self.sim_data.get_signal("Web", from_t=cycle_start)[0]
            if web < 0.5 * self.sim_data.vdd or i == 0:
                # flop may not have sampled if this is first clock
                continue

            start_index = np.absolute(all_time - cycle_start).argmin()
            end_index = np.absolute(all_time - cycle_end).argmin()

            for col_name, binary_signal in bitline_binary_signals.items():
                signal_trim = binary_signal[start_index:end_index + 1]
                if True not in signal_trim:
                    original_signal = bitline_signals[col_name][start_index:end_index + 1]
                    errors.append((col_name, cycle_start, max(original_signal)))
                else:
                    cross_index = np.where(signal_trim)[0][0] + start_index
                    cross_time = all_time[cross_index]
                    delays[col_name].append((cross_time - cycle_start, cycle_start))

        max_delay = 0
        for col_name, col_delays in delays.items():
            max_delay = max(max_delay, max([x[0] for x in col_delays]))

        if OPTS.debug_level > 1:
            delays_str = "\n".join(map(str, delays.items()))
            print(f"Delays:\n{delays_str}")

        if len(errors) > 0:
            print(f"Max precharge delay: {max_delay * 1e12:.3g} p")
            errors_str = "\n".join(map(str, errors))
            assert False, f"Precharge errors: {errors_str}"

        return max_delay
