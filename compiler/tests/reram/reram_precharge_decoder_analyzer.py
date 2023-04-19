#!env python3

import os

from reram_test_base import ReRamTestBase
from sim_analyzer_test import SimAnalyzerTest
from precharge_decoder_analyzer import PrechargeDecoderAnalyzer


class ReramPrechargeDecoderAnalyzer(PrechargeDecoderAnalyzer, SimAnalyzerTest, ReRamTestBase):
    sim_dir_suffix = "reram"
    valid_modes = ["reram"]

    precharge_threshold = float(os.getenv("PRECHARGE_THRESHOLD", 0.1))

    def test_analysis(self):
        self.run_analysis()

    def get_precharge_bitline_names(self):
        return ["br"]

    def get_precharge_end_time(self, cycle_start, cycle_end):
        return cycle_end

    def validate_precharge_signal(self, bitline_signal, signal_name,
                                  op_time, op_end, errors):
        rising_edges = [x for x in self.get_wordline_enable_edges() if op_time < x < op_end]
        if not rising_edges:
            return
        rising_edge = rising_edges[0]
        bitline_value = self.sim_data.get_signal(signal_name, rising_edge, rising_edge)[0]

        # will most definitely succeed since this covers entire period
        threshold = self.precharge_threshold * self.sim_data.vdd
        if bitline_value > threshold:
            errors.append(f"{signal_name}, time: {op_time * 1e9:5.3f}n,"
                          f" value: {bitline_value:3.3g}")

    def check_decoder_output(self):
        from globals import OPTS
        super().check_decoder_output()
        # ensure there is at least one enable edge per clock
        clk_times = self.get_clk_edges(rising=True)[1:]
        rising_edges = self.get_wordline_enable_edges()
        falling_edges = self.get_wordline_enable_edges(rising=False)

        def locate_edge_in_range(edges):
            for edge in edges:
                if cycle_start < edge < cycle_end:
                    return edge
            return None

        min_edge = OPTS.min_wordline_edge_width * 1e-9

        errors = []

        for cycle_start, cycle_end in zip(clk_times[:-1], clk_times[1:]):
            rising_edge = locate_edge_in_range(rising_edges)
            falling_edge = locate_edge_in_range(falling_edges)
            if rising_edge is None:
                errors.append(f"No wordline edge at {cycle_start * 1e9}")
            elif (falling_edge is not None and rising_edge > falling_edge and
                  rising_edge - falling_edge < min_edge):
                width = (rising_edge - falling_edge) * 1e9
                errors.append(f"Insufficient wordline edge at {cycle_start * 1e9} = {width} ns")

        if errors:
            assert False, "\n".join(errors)


if __name__ == "__main__":
    ReramPrechargeDecoderAnalyzer.parse_options()
    ReramPrechargeDecoderAnalyzer.run_tests(__name__)
