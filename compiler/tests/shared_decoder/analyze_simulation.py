#!/bin/env python3
import json
import logging
import os
import re
import time

import matplotlib
import numpy as np

matplotlib.use("Qt5Agg")
from matplotlib import pyplot as plt

from shared_simulator import create_arg_parser, parse_options, get_sim_directory, \
    CMOS_MODE, PUSH_MODE, SOT_MODE, SOTFET_MODE
import sim_analyzer
from sim_analyzer import measure_delay_from_stim_measure


def load_events(op_name):
    event_pattern = r"-- {}.*\[(.*)\]".format(op_name)
    matches = sim_analyzer.search_file(sim_analyzer.stim_file, event_pattern)
    events_ = []

    for match in matches:
        split_str = match.split(",")
        addr_, row_, col_index_, bank_ = [int(x) for x in split_str[:4]]
        event_time_, event_period_, event_duty_ = [float(x) for x in split_str[4:]]
        events_.append((event_time_ * 1e-9, addr_, event_period_ * 1e-9, event_duty_, row_,
                        col_index_, bank_))

    return events_


def get_analysis_bit(delays_):
    """Use col with max delay if verbose save or use specified bit"""
    if options.analysis_bit_index is None:
        max_delay_bit_ = (word_size - 1) - np.argmax(delays_)
        if max_delay_bit_ in probe_bits:
            return max_delay_bit_
        return probe_bits[-1]
    return probe_bits[options.analysis_bit_index]


def get_max_pattern_delay(pattern, *args, edge=None, clk_buf=False):
    if not pattern:  # pattern not saved
        return -1
    net = pattern.format(bank, *args)
    delay_func = (sim_analyzer.clk_to_bus_delay
                  if clk_buf else sim_analyzer.clk_bar_to_bus_delay)
    return delay_func(net, start_time, end_time, num_bits=1, edgetype2=edge)


def get_probe(probe_key, net, bank=None, col=None, bit=None):
    probes = voltage_probes[probe_key]
    if bank is not None:
        probes = probes[str(bank)]
    if net is not None:
        probes = probes[net]

    col_bit = col if col is not None else bit
    if isinstance(probes, dict):
        probe = probes[str(col_bit)]
    elif len(probes) == 1:
        probe = probes[0]
    else:
        container = probe_cols if col is not None else probe_bits
        col_bit_index = container.index(col_bit)
        probe = probes[col_bit_index]
    return probe


def voltage_probe_delay(probe_key, net, bank_=None, col=None, bit=None,
                        edge=None, clk_buf=False):
    probe = get_probe(probe_key, net, bank_, col, bit)
    delay_func = (sim_analyzer.clk_to_bus_delay
                  if clk_buf else sim_analyzer.clk_bar_to_bus_delay)
    return delay_func(probe, start_time, end_time, num_bits=1, edgetype2=edge)


def print_max_delay(desc, val):
    if val > 0:
        print("{} delay = {:.4g}p".format(desc, val * 1e12))


plot_exclusions = ["sense_en", "rwl_en", "bl_out"]


def plot_sig(signal_name, from_t, to_t, label):
    for excl in plot_exclusions:
        if excl in signal_name:
            return
    try:
        print(signal_name)
        signal_name = sim_data.convert_signal_name(signal_name)
        signal = sim_data.get_signal_time(signal_name, from_t=from_t, to_t=to_t)
        plt.plot(*signal, label=label)
    except Exception as er:
        print("Signal {} not found".format(signal_name))


def get_address_data(address, time):
    return original_get_address(address, time, state_probes, data_thresh)


original_get_address = sim_analyzer.get_address_data
sim_analyzer.get_address_data = get_address_data

arg_parser = create_arg_parser()
arg_parser.add_argument("-v", "--verbose", action="count", default=0)
mode, options = parse_options(arg_parser)
openram_temp = get_sim_directory(options, mode) + ""
cmos = mode in [CMOS_MODE, PUSH_MODE]
push = mode == PUSH_MODE

word_size = options.word_size
schematic = options.schematic

if options.verbose > 0:
    log_level = int(max(0, 2 - options.verbose) * 10)
else:
    log_level = logging.ERROR

logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

print("Word-size = ", word_size)

# Take overlap between cycles into account
read_settling_time = 50e-12
write_settling_time = 150e-12

logging.info("Simulation Dir = {}".format(openram_temp))

if options.spice_name == "hspice":
    sim_analyzer.measure_file_name = "timing.lis"
    sim_analyzer.transient_file_name = "timing.tr0"
sim_analyzer.setup(num_cols_=options.num_cols, num_rows_=options.num_rows,
                   sim_dir_=openram_temp)

two_bank_dependent = bool(sim_analyzer.search_file(sim_analyzer.stim_file,
                                                   r"two_bank_dependent = ([0-1])"))

words_per_row = int(options.num_cols / options.word_size)
if two_bank_dependent:
    num_words = words_per_row * options.num_rows
else:
    num_words = words_per_row * options.num_rows * options.num_banks
address_width = int(np.log2(num_words))

sim_analyzer.word_size = options.word_size

state_probes = json.load(open(os.path.join(openram_temp, "state_probes.json"), "r"))
voltage_probes = json.load(open(os.path.join(openram_temp, "voltage_probes.json"), "r"))
current_probes = json.load(open(os.path.join(openram_temp, "current_probes.json"), "r"))
with open(os.path.join(openram_temp, "sim_saves.txt"), "w") as f:
    f.write("\n".join(sim_analyzer.all_saved_list))

data_pattern = "D[{}]"
mask_pattern = "mask[{}]"
sim_analyzer.data_pattern = data_pattern

logging.info("Simulation end: " + time.ctime(os.path.getmtime(sim_analyzer.stim_file)))

sim_data = sim_analyzer.sim_data

sim_data.thresh = 0.45
data_thresh = sim_data.thresh if cmos else 0

setup_time = 0.015e-9

address_pattern = "A[{}]"

probe_cols_str = sim_analyzer.search_file(sim_analyzer.stim_file,
                                          r"Probe cols = \[(.*)\]")
probe_cols = list(map(int, probe_cols_str.split(",")))

probe_bits_str = sim_analyzer.search_file(sim_analyzer.stim_file,
                                          r"Probe bits = \[(.*)\]")
probe_bits = list(map(int, probe_bits_str.split(",")))

if __name__ == "__main__":

    sim_analyzer.clk_reference = sim_data.convert_signal_name(voltage_probes["clk_probe"])

    area = float(sim_analyzer.search_file(sim_analyzer.stim_file, r"Area=([0-9\.]+)um2"))

    all_read_events = load_events("Read") if not options.skip_read_check else []
    all_write_events = load_events("Write") if not options.skip_write_check else []

    # Precharge and Decoder delay
    max_decoder_delay = 0
    max_precharge = 0
    max_clk_to_decoder_in = 0
    for event in all_read_events + all_write_events:
        max_dec_, dec_delays = measure_delay_from_stim_measure("decoder_a[0-9]+",
                                                               max_delay=0.9 * event[2],
                                                               event_time=event[0])
        max_decoder_delay = max(max_decoder_delay, max_dec_)

        max_prech_, prech_delays = measure_delay_from_stim_measure("precharge_delay",
                                                                   max_delay=0.9 * event[2],
                                                                   event_time=event[0])
        max_precharge = max(max_precharge, max_prech_)

        if push:
            max_clk_dec_, _ = measure_delay_from_stim_measure("decoder_in[0-9]+", max_delay=0.9 * event[2],
                                                              event_time=event[0])
            max_clk_to_decoder_in = max(max_clk_to_decoder_in, max_clk_dec_)

    print("\nPrecharge delay = {:.2f}p".format(max_precharge / 1e-12))

    if push:
        print("Clk to dec_in = {:.2f}p".format(max_clk_to_decoder_in / 1e-12))
        print("Decoder enable to dec_out = {:.2f}p".format(max_decoder_delay / 1e-12))
    else:
        print("Decoder delay = {:.2f}p".format(max_decoder_delay / 1e-12))

    if push:
        max_decoder_delay, max_clk_to_decoder_in = max_clk_to_decoder_in, max_decoder_delay

    # Analyze Reads

    print("----------------Read Analysis---------------")
    max_read_event = None
    for read_event in all_read_events:
        print("Read {} at time: {:.4g} n".format(read_event[1], read_event[0] * 1e9))
        correct = sim_analyzer.verify_read_event(read_event[0], read_event[1],
                                                 read_event[2] + read_settling_time,
                                                 read_event[3], negate=False)
        if not correct:
            max_read_event = read_event

    max_dout = 0

    max_read_bit_delays = [0] * word_size
    if options.analysis_op_index is not None:
        analysis_events = all_read_events[options.analysis_op_index:options.analysis_op_index + 1]
    elif max_read_event is not None:
        analysis_events = [max_read_event]
    else:
        analysis_events = all_read_events
    for index, read_event in enumerate(analysis_events):
        d_delays = sim_analyzer.clk_bar_to_bus_delay(data_pattern, read_event[0],
                                                     read_event[0] + read_event[2] +
                                                     read_settling_time, num_bits=word_size)

        if max(d_delays) > max_dout or index == 0:
            max_read_event = read_event
            max_dout = max(d_delays)
            max_read_bit_delays = d_delays

    print("clk_bar to Read bus out delay = {:.2f}p".format(max_dout / 1e-12))

    total_read = max(max_precharge, max_decoder_delay) + max_dout
    print("Total Read delay = {:.2f}p".format(total_read / 1e-12))

    read_energies = [sim_analyzer.measure_energy((x[0], x[0] + x[2])) for x in all_read_events]
    if not read_energies:
        read_energies = [0]

    print("Max read energy = {:.2f} pJ".format(max(read_energies) / 1e-12))

    # analyze writes
    print("----------------Write Analysis---------------")

    max_write_event = None
    for write_event_ in all_write_events:
        print("Write {} at time: {:.4g} n".format(write_event_[1], write_event_[0] * 1e9))
        correct = sim_analyzer.verify_write_event(write_event_[0], write_event_[1],
                                                  write_event_[2] + write_settling_time,
                                                  write_event_[3], negate=False)
        if not correct:
            max_write_event = write_event_

    write_energies = [sim_analyzer.measure_energy((x[0], x[2] + x[0])) for x in all_write_events]
    if not write_energies:
        write_energies = [0]

    # Write delay
    max_q_delay = 0
    max_write_bit_delays = [0] * word_size

    if options.analysis_op_index is not None:
        analysis_events = all_write_events[options.analysis_op_index:options.analysis_op_index + 1]
    elif max_write_event is not None:
        analysis_events = [max_write_event]
    else:
        analysis_events = all_write_events

    for index, write_event in enumerate(analysis_events):
        max_valid_delay = (1 + write_event[3]) * write_event[2]
        max_q_, q_delays = sim_analyzer. \
            measure_delay_from_stim_measure("state_delay", event_time=write_event[0],
                                            max_delay=max_valid_delay,
                                            index_pattern="a[0-9]+_c(?P<bit>[0-9]+)_")
        if max_q_ > max_q_delay or index == 0:
            max_q_delay = max_q_
            max_write_event = write_event
            max_write_bit_delays = q_delays
    # max_write_event = all_write_events[0]

    print("Q state delay = {:.4g} ps, address = {}, t = {:.4g} ns".
          format(max_q_delay / 1e-12, max_write_event[1], max_write_event[0] * 1e9))

    total_write = max(max_precharge, max_decoder_delay) + max_q_delay
    print("Total Write delay = {:.2f} ps".format(total_write / 1e-12))
    print("Max write energy = {:.2f} pJ".format(max(write_energies) / 1e-12))

    print("----------------Critical Paths---------------")

    # write analysis:
    max_write_bit = get_analysis_bit(max_write_bit_delays)

    write_address = max_write_event[1]
    write_period = max_write_event[2]
    write_start_time = max_write_event[0]
    max_write_row = max_write_event[4]

    write_end_time = write_start_time + write_period + write_settling_time + 0.2e-9

    q_net = "v({})".format(state_probes[str(write_address)][max_write_bit])

    max_write_col = int(re.search("r[0-9]+_c([0-9]+)", q_net).group(1))
    max_write_bit = int(max_write_col / words_per_row)
    write_bank = int(re.search("Xbank([0-1]+)", q_net).group(1))

    # col = max_write_bit *
    start_time = write_start_time
    end_time = write_end_time
    bank = write_bank

    write_en_delay = voltage_probe_delay("control_buffers", "write_en", bank,
                                         bit=max_write_bit, edge=sim_data.RISING_EDGE)

    flop_out_delay = voltage_probe_delay("write_driver_array", "data", bank, bit=max_write_bit)
    bl_delay = voltage_probe_delay("bl", None, bank,
                                   col=max_write_col, edge=sim_data.FALLING_EDGE)
    br_delay = voltage_probe_delay("br", None, bank,
                                   col=max_write_col, edge=sim_data.FALLING_EDGE)
    q_delay = get_max_pattern_delay(q_net)

    print("\nWrite Critical Path: t = {:.3g}n row={} bit={} bank={}\n".format(max_write_event[0], max_write_row,
                                                                              max_write_bit, bank))
    print_max_delay("Write EN", write_en_delay)
    if "write_en_bar" in voltage_probes["control_buffers"]:
        write_en_bar_delay = voltage_probe_delay("control_buffers", "write_en_bar", bank,
                                                 max_write_bit, edge=sim_data.FALLING_EDGE)
        print_max_delay("Write ENB", write_en_bar_delay)
    print_max_delay("Flop out", flop_out_delay)
    print_max_delay("BL", bl_delay)
    print_max_delay("BR", br_delay)
    print_max_delay("Q", q_delay)

    # Read analysis
    max_read_bit = get_analysis_bit(max_read_bit_delays)

    max_read_address = max_read_event[1]
    # max_read_row = max_read_event[4]
    max_read_row = options.num_rows - 1
    max_read_period = max_read_event[2]
    read_start_time = max_read_event[0]
    read_end_time = read_start_time + max_read_period + read_settling_time + 0.1e-9

    read_q_net = "v({})".format(state_probes[str(max_read_address)][max_read_bit])
    bank = read_bank = int(re.search("Xbank([0-1]+)", read_q_net).group(1))

    max_read_col = int(re.search("r[0-9]+_c([0-9]+)", read_q_net).group(1))
    max_read_bit = int(max_read_col / words_per_row)
    sense_mod_index = max_read_bit

    start_time = read_start_time
    end_time = read_end_time

    print("\nRead Critical Path: t = {:.3g}n row={} bit={} bank={} \n".
          format(max_read_event[0], max_read_row, max_read_bit, bank))
    wordline_en = "wordline_en" if cmos else "rwl_en"

    wordline_en_delay = voltage_probe_delay("control_buffers", wordline_en, bank,
                                            bit=max_read_row, edge=sim_data.RISING_EDGE)
    wordline_delay = voltage_probe_delay("wl", None, None, bit=max_read_address,
                                         edge=sim_data.RISING_EDGE)

    sample_fall_delay = sample_rise_delay = None
    if "sample_en_bar" in voltage_probes["control_buffers"]:
        sample_fall_delay = voltage_probe_delay("control_buffers", "sample_en_bar", bank,
                                                sense_mod_index, edge=sim_data.FALLING_EDGE)
        sample_rise_delay = voltage_probe_delay("control_buffers", "sample_en_bar", bank,
                                                sense_mod_index, edge=sim_data.RISING_EDGE)

    sense_en_delay = voltage_probe_delay("control_buffers", "sense_en", bank,
                                         sense_mod_index, edge=sim_data.RISING_EDGE)

    bl_delay = voltage_probe_delay("sense_amp_array", "bl", bank, sense_mod_index)
    if "br" in voltage_probes["sense_amp_array"][str(bank)]:
        br_delay = voltage_probe_delay("sense_amp_array", "br", bank, sense_mod_index)
    else:
        br_delay = voltage_probe_delay("br", None, bank, col=max_read_col)

    print_max_delay("Wordline EN", wordline_en_delay)
    print_max_delay("Wordline ", wordline_delay)
    if sample_rise_delay is not None and sample_rise_delay is not None:
        print_max_delay("Sample Fall", sample_fall_delay)
        print_max_delay("Sample Rise", sample_rise_delay)
    print_max_delay("Sense EN", sense_en_delay)
    print_max_delay("BL", bl_delay)
    print_max_delay("BR", br_delay)

    if push:
        sense_bit = int(max_read_bit / 2)
    else:
        sense_bit = max_read_bit

    sense_out_delay = voltage_probe_delay("sense_amp_array", "dout", bank, sense_bit)
    print_max_delay("Sense out", sense_out_delay)

    # Plots
    if options.plot is not None:
        logging.getLogger('matplotlib').setLevel(logging.WARNING)
        if options.plot == "write":
            bit = max_write_bit
            col = max_write_col
            start_time = write_start_time
            end_time = write_end_time
            row = max_write_row
            bank = write_bank
            address = write_address
        else:
            bit = max_read_bit
            col = max_read_col
            start_time = read_start_time
            end_time = read_end_time
            q_net = read_q_net
            row = max_read_row
            bank = read_bank
            address = max_read_address

        plot_sig(sim_analyzer.clk_reference, from_t=start_time, to_t=end_time, label="clk_buf")


        def format_sig(key, net, bit_=None):
            if bit_ is None:
                bit_ = bit
            return get_probe(key, net, bank, bit_)


        plot_sig(format_sig("bl", None, col), from_t=start_time, to_t=end_time, label="bl")
        plot_sig(format_sig("br", None, col), from_t=start_time, to_t=end_time, label="br")

        plot_sig(format_sig("sense_amp_array", "bl"),
                 from_t=start_time, to_t=end_time, label="bl_out")
        if "br" in voltage_probes["sense_amp_array"][str(bank)]:
            plot_sig(format_sig("sense_amp_array", "br"),
                     from_t=start_time, to_t=end_time, label="br_out")

        if options.plot == "write":
            plot_sig(format_sig("control_buffers", "write_en"),
                     from_t=start_time, to_t=end_time, label="write_en")
            # plot_sig(format_sig("control_buffers", "clk_buf"),
            #          from_t=start_time, to_t=end_time, label="flop_clk")
            # plot_sig(format_sig("write_driver_array", "data"),
            #          from_t=start_time, to_t=end_time, label="flop_out")
        else:
            if sample_rise_delay is not None:
                plot_sig(format_sig("control_buffers", "sample_en_bar"),
                         from_t=start_time, to_t=end_time, label="sample")
            if mode == SOT_MODE:
                plot_sig(format_sig("sense_amp_array", "vref"),
                         from_t=start_time, to_t=end_time, label="vref")
                plot_sig(format_sig("sense_amp_array", "vdata"),
                         from_t=start_time, to_t=end_time, label="vdata")
            if mode in [SOT_MODE, SOTFET_MODE]:
                plot_sig(format_sig("control_buffers", "rwl_en", bit_=max_read_row),
                         from_t=start_time, to_t=end_time, label="rwl_en")
            plot_sig(format_sig("control_buffers", "sense_en"),
                     from_t=start_time, to_t=end_time, label="sense_en")
            plot_sig(format_sig("sense_amp_array", "dout"),
                     from_t=start_time, to_t=end_time, label="sense_out")
            plot_sig(data_pattern.format(bit),
                     from_t=start_time, to_t=end_time, label="D")
        if not cmos and options.plot == "write":
            wl_name = "wwl"
        else:
            wl_name = "wl"
        plot_sig(voltage_probes[wl_name][str(address)],
                 from_t=start_time, to_t=end_time, label="wl[{}]".format(row))
        # plot_sig(wordline_en_pattern.format(bank),
        #                                    from_t=start_time, to_t=end_time, label="wl_en")
        plot_sig(q_net, from_t=start_time, to_t=end_time, label="Q")
        #            plot_sig("clk", from_t=start_time, to_t=end_time, label="clk")
        plt.axhline(y=0.45, linestyle='--', linewidth=0.5)
        plt.axhline(y=0.9, linestyle='--', linewidth=0.5)

        plt.grid()
        plt.legend(loc="center left", fontsize="x-small")
        plt.title("{}: bit = {} col = {} addr = {}".format(os.path.basename(openram_temp),
                                                           bit, col, address))
        if not options.verbose_save:
            print("Available bits: {}".format(", ".join(map(str, probe_bits))))

        sot_write = options.plot == "write" and not cmos

        # psf_reader.get_dpi() TODO segfaults
        # psf_reader.move_plot(monitor=0, maximized=False)
        plt.show(block=not sot_write)

        if sot_write:
            write_current_net = current_probes["bitcell_array"][str(address)][str(col)]
            write_current_net = "i1({})".format(write_current_net)
            write_current_time = sim_data.get_signal_time(write_current_net, from_t=start_time,
                                                          to_t=end_time)
            # write_current = write_current_time[1] / max(abs(write_current_time[1]))
            write_current = write_current_time[1] * 1e6
            if not options.schematic:
                write_current *= 2
            plt.figure()
            plt.plot(write_current_time[0], write_current, label="current")
            plt.ylabel("Write Current (uA)")
            plt.grid()
            plt.show()
