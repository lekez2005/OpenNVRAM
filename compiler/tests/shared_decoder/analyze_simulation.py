#!/bin/env python
import json
import logging
import os
import re
import time

import matplotlib
import numpy as np

matplotlib.use("Qt5Agg")
from matplotlib import pyplot as plt

from shared_simulator import create_arg_parser, parse_options, get_sim_directory, CMOS_MODE
import sim_analyzer
from sim_analyzer import measure_delay_from_stim_measure


def get_address_data(address, time):
    return sim_analyzer.get_address_data(address, time, state_probes, data_thresh)


def pattern_from_saved(pattern, *args):
    pattern = re.search(pattern, sim_analyzer.all_saved_signals)
    if pattern is None:
        return ""
    pattern = pattern.group(0)
    for i in range(0, len(args), 2):
        pattern = re.sub(args[i], args[i + 1], pattern)
    pattern = re.sub("Xbank[01]+", "Xbank{0}", pattern)
    return pattern


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
        if verbose_save:
            return (word_size - 1) - np.argmax(delays_)
        else:
            return probe_bits[-1]
    return probe_bits[options.analysis_bit_index]


def get_address_data(address, time):
    return original_get_address(address, time, state_probes, data_thresh)


original_get_address = sim_analyzer.get_address_data
sim_analyzer.get_address_data = get_address_data

arg_parser = create_arg_parser()
arg_parser.add_argument("-v", "--verbose", action="count", default=0)
mode, options = parse_options(arg_parser)
openram_temp = get_sim_directory(options, mode) + ""
cmos = mode == CMOS_MODE

word_size = options.word_size
schematic = options.schematic

if options.verbose > 0:
    log_level = int(max(0, 2 - options.verbose) * 10)
else:
    log_level = logging.ERROR

logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

print("Word-size = ", word_size)

verbose_save = options.verbose_save

words_per_row = int(options.num_cols / options.word_size)
num_words = words_per_row * options.num_rows * options.num_banks

address_width = int(np.log2(num_words))

# Take overlap between cycles into account
read_settling_time = 150e-12
write_settling_time = 500e-12

logging.info("Simulation Dir = {}".format(openram_temp))

sim_analyzer.setup(num_cols_=options.num_cols, num_rows_=options.num_rows,
                   sim_dir_=openram_temp)

states_file = os.path.join(openram_temp, "state_probes.json")
logging.info("Simulation end: " + time.ctime(os.path.getmtime(sim_analyzer.stim_file)))

sim_data = sim_analyzer.sim_data

sim_data.thresh = 0.45
data_thresh = sim_data.thresh if cmos else 0

with open(states_file, "r") as states_file_:
    state_probes = json.load(states_file_)

setup_time = 0.015e-9

mask_pattern = "mask[{}]"

if not schematic:

    if cmos:
        wordline_pattern = pattern_from_saved("v\(\S+wl\S+Xbitcell_array\S+\)", "wl\[[0-9]+\]", "wl[{1}]",
                                              "r[0-9]+", "r{1}")
        wordline_en_pattern = pattern_from_saved("v\(\S+wordline_en\S+Xwordline_driver\S+\)")
    else:
        wordline_en_pattern = pattern_from_saved("v\(\S+wwl_en\S+Xwwl_driver\S+\)")
        rwl_en_pattern = pattern_from_saved("v\(\S+rwl_en\S+Xrwl_driver\S+\)")
        wordline_pattern = pattern_from_saved("v\(\S+wwl\S+Xbitcell_array\S+\)", "wwl\[[0-9]+\]", "wwl[{1}]",
                                              "r[0-9]+", "r{1}")
        rwl_pattern = pattern_from_saved("v\(\S+rwl\S+Xbitcell_array\S+\)", "rwl\[[0-9]+\]", "rwl[{1}]",
                                         "r[0-9]+", "r{1}")
    write_en_pattern = pattern_from_saved("v\(\S+write_en(?!_bar)\S+Xdriver\S+\)", "Xdriver_[0-9]+", "Xdriver_{1}")

    write_en_bar_pattern = pattern_from_saved("v\(\S+write_en_bar\S+Xdriver\S+\)", "Xdriver_[0-9]+", "Xdriver_{1}")

    bl_pattern = pattern_from_saved("v\(\S+bl\S+Xbitcell\S+\)", "c[0-9]+", "c{1}", "\[[0-9]+\]", "[{1}]")
    br_pattern = pattern_from_saved("v\(\S+br\S+Xbitcell\S+\)", "c[0-9]+", "c{1}", "\[[0-9]+\]", "[{1}]")
    if words_per_row > 1:
        bl_out_pattern = pattern_from_saved("v\(\S+bl_out\S+Xsa\S+\)", "bl_out\[[0-9]+\]", "bl_out[{1}]",
                                            "Xsa_d[0-9]+", "Xsa_d{1}")
        br_out_pattern = pattern_from_saved("v\(\S+br_out\S+Xsa\S+\)", "br_out\[[0-9]+\]", "br_out[{1}]",
                                            "Xsa_d[0-9]+", "Xsa_d{1}")

    flop_clk_in_pattern = pattern_from_saved("v\(\S+clk_bar\S+Xdata_in\S+\)", "dff[0-9]+", "dff{1}")

    sense_en_pattern = pattern_from_saved("v\(\S+sense_en(?!_bar)\S+Xsa\S+\)", "Xsa_d[0-9]+", "Xsa_d{1}")
    sample_en_bar_pattern = pattern_from_saved("v\(\S+sample_en_bar\S+Xsa\S+\)", "Xsa_d[0-9]+", "Xsa_d{1}")

    and_out_pattern = pattern_from_saved("v\(\S+and_out\S+Xsense_amp_array\S+\)", "Xsa_d[0-9]+", "Xsa_d{1}",
                                         "and_out\[[0-9]+\]", "and_out[{1}]")

data_pattern = "D[{}]"
sim_analyzer.data_pattern = data_pattern

write_driver_in_pattern = pattern_from_saved("v\(\S+data_in\S+Xdriver\S+\)", "Xdriver_[0-9]+", "Xdriver_{1}",
                                             "\[[0-9]+\]", "[{1}]")

address_pattern = "A[{}]"

probe_cols_str = sim_analyzer.search_file(sim_analyzer.stim_file,
                                          r"Probe cols = \[(.*)\]")
probe_cols = list(map(int, probe_cols_str.split(",")))
if verbose_save:
    probe_bits = list(range(word_size))
else:
    probe_bits = [int(x / words_per_row) for x in probe_cols]

if __name__ == "__main__":

    clk_reference = "v(" + re.search(r".meas tran {}.* TRIG v\((\S+)\) VAL".
                                     format("PRECHARGE"), sim_analyzer.stim_str).group(1) + ")"

    area = float(sim_analyzer.search_file(sim_analyzer.stim_file, r"Area=([0-9\.]+)um2"))

    all_read_events = load_events("Read") if not options.skip_read_check else []
    all_write_events = load_events("Write") if not options.skip_write_check else []

    # Precharge and Decoder delay
    max_decoder_delay = 0
    max_precharge = 0
    for event in all_read_events + all_write_events:
        max_dec_, dec_delays = measure_delay_from_stim_measure("decoder",
                                                               max_delay=0.9 * event[2],
                                                               event_time=event[0])
        max_decoder_delay = max(max_decoder_delay, max_dec_)

        max_prech_, prech_delays = measure_delay_from_stim_measure("precharge_delay",
                                                                   max_delay=0.9 * event[2],
                                                                   event_time=event[0])
        max_precharge = max(max_precharge, max_prech_)

    print("\nDecoder delay = {:.2f}p".format(max_decoder_delay / 1e-12))
    print("Precharge delay = {:.2f}p".format(max_precharge / 1e-12))

    # Analyze Reads

    print("----------------Read Analysis---------------")
    for read_event in all_read_events:
        print("Read at time: {:.4g} n".format(read_event[0] * 1e9))
        sim_analyzer.verify_read_event(read_event[0], read_event[1],
                                       read_event[2] + read_settling_time,
                                       read_event[3], negate=not cmos)

    max_dout = 0
    max_read_event = all_read_events[-1] if all_read_events else all_write_events[-1]
    max_read_bit_delays = [0] * word_size
    if options.analysis_op_index is not None:
        analysis_events = all_read_events[options.analysis_op_index:options.analysis_op_index + 1]
    else:
        analysis_events = all_read_events
    for read_event in analysis_events:
        d_delays = sim_analyzer.clk_bar_to_bus_delay(data_pattern, read_event[0],
                                                     read_event[0] + read_event[2] +
                                                     read_settling_time, num_bits=word_size)

        if max(d_delays) > max_dout:
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

    for write_event_ in all_write_events:
        print("Write at time: {:.4g} n".format(write_event_[0] * 1e9))
        sim_analyzer.verify_write_event(write_event_[0], write_event_[1],
                                        write_event_[2] + write_settling_time,
                                        write_event_[3], negate=not cmos)

    write_energies = [sim_analyzer.measure_energy((x[0], x[2] + x[0])) for x in all_write_events]
    if not write_energies:
        write_energies = [0]

    # Write delay
    max_q_delay = 0
    max_write_event = all_write_events[1] if all_write_events else all_read_events[-1]
    max_write_bit_delays = [0] * word_size

    if options.analysis_op_index is not None:
        analysis_events = all_write_events[options.analysis_op_index:options.analysis_op_index + 1]
    else:
        analysis_events = all_write_events

    for write_event in analysis_events:
        max_valid_delay = (1 + write_event[3]) * write_event[2]
        max_q_, q_delays = sim_analyzer. \
            measure_delay_from_stim_measure("state_delay", event_time=write_event[0],
                                            max_delay=max_valid_delay,
                                            index_pattern="a[0-9]+_c(?P<bit>[0-9]+)_")
        if max_q_ > max_q_delay:
            max_q_delay = max_q_
            max_write_event = write_event
            max_write_bit_delays = q_delays

    print("Q state delay = {:.3g} ps, address = {}, t = {:.3g} ns".
          format(max_q_delay / 1e-12, max_write_event[1], max_write_event[0] * 1e9))

    total_write = max(max_precharge, max_decoder_delay) + max_q_delay
    print("Total Write delay = {:.2f} ps".format(total_write / 1e-12))
    print("Max write energy = {:.2f} pJ".format(max(write_energies) / 1e-12))

    if not schematic:

        print("----------------Critical Paths---------------")

        print("\nWrite Critical Path: t = {:.3g}n\n".format(max_write_event[0]))

        start_time = end_time = 0
        bank = 0


        def get_max_pattern_delay(pattern, *args, edge=None):
            if not pattern:  # pattern not saved
                return -1
            net = pattern.format(bank, *args)
            return sim_analyzer.clk_bar_to_bus_delay(net, start_time, end_time,
                                                     num_bits=1, edgetype2=edge)


        def print_max_delay(desc, val):
            if val > 0:
                print("{} delay = {:.3g}p".format(desc, val * 1e12))


        def plot_sig(signal_name, from_t, to_t, label):
            try:
                signal = sim_data.get_signal_time(signal_name, from_t=from_t, to_t=to_t)
                plt.plot(*signal, label=label)
            except Exception as er:
                print("Signal {} not found".format(signal_name))


        # write analysis:
        max_write_bit = get_analysis_bit(max_write_bit_delays)

        write_address = max_write_event[1]
        write_period = max_write_event[2]
        write_start_time = max_write_event[0]
        max_write_row = max_write_event[4]
        write_bank = max_write_event[6]
        write_end_time = write_start_time + write_period + write_settling_time + 0.2e-9

        q_net = "v({})".format(state_probes[str(write_address)][max_write_bit])

        max_write_col = int(re.search("r[0-9]+_c([0-9]+)", q_net).group(1))

        # col = max_write_bit *
        start_time = write_start_time
        end_time = write_end_time
        bank = write_bank

        write_en_delay = get_max_pattern_delay(write_en_pattern, max_write_bit, edge=sim_data.RISING_EDGE)
        write_en_bar_delay = get_max_pattern_delay(write_en_bar_pattern, max_write_bit, edge=sim_data.FALLING_EDGE)
        flop_out_delay = get_max_pattern_delay(write_driver_in_pattern, max_write_bit)
        bl_delay = get_max_pattern_delay(bl_pattern, max_write_col, edge=sim_data.FALLING_EDGE)
        br_delay = get_max_pattern_delay(br_pattern, max_write_col, edge=sim_data.FALLING_EDGE)
        q_delay = get_max_pattern_delay(q_net)

        print_max_delay("Write EN", write_en_delay)
        print_max_delay("Write ENB", write_en_bar_delay)
        print_max_delay("Flop out", flop_out_delay)
        print_max_delay("BL", bl_delay)
        print_max_delay("BR", br_delay)
        print_max_delay("Q", q_delay)

        # max_read_event = all_read_events[4]
        print("\nRead Critical Path: t = {:.3g}n\n".format(max_read_event[0]))

        # Read analysis
        max_read_bit = get_analysis_bit(max_read_bit_delays)

        max_read_address = max_read_event[1]
        max_read_row = max_read_event[4]
        max_read_period = max_read_event[2]
        read_start_time = max_read_event[0]
        read_end_time = read_start_time + max_read_period + read_settling_time + 0.1e-9
        read_bank = max_read_event[6]

        read_q_net = "v({})".format(state_probes[str(max_read_address)][max_read_bit])

        max_read_col = int(re.search("r[0-9]+_c([0-9]+)", read_q_net).group(1))

        start_time = read_start_time
        end_time = read_end_time
        bank = read_bank

        wordline_en_delay = get_max_pattern_delay(wordline_en_pattern, edge=sim_data.RISING_EDGE)
        wordline_delay = get_max_pattern_delay(wordline_pattern, max_read_row, edge=sim_data.RISING_EDGE)
        sample_fall_delay = get_max_pattern_delay(sample_en_bar_pattern, max_read_bit, edge=sim_data.FALLING_EDGE)
        sample_rise_delay = get_max_pattern_delay(sample_en_bar_pattern, max_read_bit, edge=sim_data.RISING_EDGE)
        sense_en_delay = get_max_pattern_delay(sense_en_pattern, max_read_bit)
        if words_per_row == 1:
            bl_delay = get_max_pattern_delay(bl_pattern, max_read_bit)
            br_delay = get_max_pattern_delay(br_pattern, max_read_bit)
            bl_plot_pattern = bl_pattern
            br_plot_pattern = br_pattern
        else:
            bl_delay = get_max_pattern_delay(bl_out_pattern, max_read_bit)
            br_delay = get_max_pattern_delay(br_out_pattern, max_read_bit)
            bl_plot_pattern = bl_out_pattern
            br_plot_pattern = br_out_pattern
        if not cmos and not options.plot == "write":
            wordline_pattern = rwl_pattern
            wordline_en_pattern = rwl_en_pattern

        print_max_delay("Wordline EN", wordline_en_delay)
        print_max_delay("Wordline ", wordline_delay)
        print_max_delay("Sample Fall", sample_fall_delay)
        print_max_delay("Sample Rise", sample_rise_delay)
        print_max_delay("Sense EN", sense_en_delay)
        print_max_delay("BL", bl_delay)
        print_max_delay("BR", br_delay)

        and_out_signal = and_out_pattern.format(bank, max_read_bit)
        if and_out_signal in sim_analyzer.all_saved_signals:
            and_out_delay = get_max_pattern_delay(and_out_pattern, max_read_bit)
            print_max_delay("Sense out", and_out_delay)

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

            plot_sig(clk_reference, from_t=start_time, to_t=end_time, label="clk_buf")

            plot_sig(bl_pattern.format(bank, col),
                     from_t=start_time, to_t=end_time, label="bl")
            plot_sig(br_pattern.format(bank, col),
                     from_t=start_time, to_t=end_time, label="br")
            if words_per_row > 1:
                plot_sig(bl_out_pattern.format(bank, bit),
                         from_t=start_time, to_t=end_time, label="bl_out")
                plot_sig(br_out_pattern.format(bank, bit),
                         from_t=start_time, to_t=end_time, label="br_out")

            if options.plot == "write":
                # plot_sig(write_en_pattern.format(bank, max_write_bit),
                #                                    from_t=start_time, to_t=end_time, label="write_en")
                # plot_sig(write_en_bar_pattern.format(bank, max_write_bit),
                #                                    from_t=start_time, to_t=end_time, label="write_en_bar")
                if verbose_save:
                    plot_sig(flop_clk_in_pattern.format(bank, max_write_bit),
                             from_t=start_time, to_t=end_time, label="flop_clk")
                    plot_sig(write_driver_in_pattern.format(bank, max_write_bit),
                             from_t=start_time, to_t=end_time, label="flop_out")
            else:
                plot_sig(sample_en_bar_pattern.format(bank, max_read_bit),
                         from_t=start_time, to_t=end_time, label="sample")
                plot_sig(sense_en_pattern.format(bank, max_read_bit),
                         from_t=start_time, to_t=end_time, label="sense_en")
                plot_sig(and_out_pattern.format(bank, max_read_bit),
                         from_t=start_time, to_t=end_time, label="and_out")
            plot_sig(wordline_pattern.format(bank, row),
                     from_t=start_time, to_t=end_time, label="wl[{}]".format(row))
            # plot_sig(wordline_en_pattern.format(bank),
            #                                    from_t=start_time, to_t=end_time, label="wl_en")
            plot_sig(q_net, from_t=start_time, to_t=end_time, label="Q")
            #            plot_sig("clk", from_t=start_time, to_t=end_time, label="clk")
            plt.axhline(y=0.45, linestyle='--', linewidth=0.5)
            plt.axhline(y=0.9, linestyle='--', linewidth=0.5)

            if options.plot == "write" and not cmos:
                write_current_net = q_net.replace("state", "M1:d").replace("v(", "").replace(")", "")
                write_current_time = sim_data.get_signal_time(write_current_net, from_t=start_time,
                                                              to_t=end_time)
                write_current = write_current_time[1] / max(abs(write_current_time[1]))
                # write_current = write_current_time[1] * 10e6
                plt.plot(write_current_time[0], write_current, label="current")

            plt.grid()
            plt.legend(loc="center left", fontsize="x-small")
            plt.title("{}: bit = {} col = {} addr = {}".format(os.path.basename(openram_temp),
                                                               bit, col, address))
            if not verbose_save:
                print("Available bits: {}".format(", ".join(map(str, probe_bits))))
            # move_plot(monitor=0, maximized=False)
            plt.show()
