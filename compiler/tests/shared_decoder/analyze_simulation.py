#!/bin/env python
import json
import logging
import os
import re
import time

import numpy as np
from matplotlib import pyplot as plt

from shared_simulator import create_arg_parser, parse_options, get_sim_directory
from psf_reader import PsfReader


def search_file(filename, pattern):
    with open(filename, 'r') as file:
        content = file.read()
        matches = re.findall(pattern, content)
        if len(matches) == 1:
            return matches[0]
        else:
            return matches


def get_command(label):
    command_pattern = re.compile('meas tran {}.*TD=(?P<start_time>\S+)n.*TD=(?P<end_time>\S+)n'.format(label),
                                 re.IGNORECASE)
    result = command_pattern.search(stim_str)
    return result


def measure_energy(times, period):
    if isinstance(times, str):
        times = float(times) * 1e-9
    if isinstance(times, float):
        times = (times, times + period)
    current = sim_data.get_signal('Vvdd:p', times[0], times[1])
    time = sim_data.slice_array(sim_data.time, times[0], times[1])
    energy = -np.trapz(current, time) * 0.9

    return energy


def measure_delay_from_stim_measure(prefix, event, max_delay=None):
    if event is not None:
        event_time = event[0]
        time_suffix = "t{:.2g}".format(event_time * 1e9).replace('.', '_')
    else:
        time_suffix = ""
    if max_delay is None:
        max_delay = 0.9 * event[2]

    pattern_str = r'{}_.*{}'.format(prefix, time_suffix) + " = (?P<delay>\S+)\s\n"

    pattern = re.compile(pattern_str)

    delays = [float(x) for x in pattern.findall(meas_str)]

    valid_delays = list(filter(lambda x: x < max_delay, delays))
    if len(valid_delays) > 0:
        max_delay = max(valid_delays)
    else:
        max_delay = 0
    return max_delay, delays


def extract_probe_pattern(meas_name):
    sample_group = re.search(".meas tran {}.* TARG v\((.+)\) VAL".format(meas_name), stim_str)
    if sample_group is None:
        return ""
    sample = sample_group.group(1)

    specific_index = re.search("\[[0-9]+\]", sample)
    if specific_index is None:
        return sample
    generic_pattern = sample.replace(specific_index.group(), "[{0}]")
    return generic_pattern


def standardize_pattern(pattern, specific_loc="", gen_loc=""):
    pattern = "v(" + pattern + ")"
    pattern = re.sub(specific_loc, gen_loc, pattern)
    return pattern


def get_address_data(address, time):
    address_probes = list(reversed(state_probes[str(address)]))
    address_probes = ["v({})".format(x) for x in address_probes]

    address_data = [sim_data.get_binary(x, time)[0] for x in address_probes]
    return address_data


def verify_write_event(write_event):
    write_time = write_event[0]
    write_address = write_event[1]
    write_period = write_event[2]
    duty_cycle = write_event[3]

    current_data = get_address_data(write_address, write_time)
    current_mask = sim_data.get_bus_binary(mask_pattern, options.word_size, write_time)

    new_data = sim_data.get_bus_binary(data_pattern, word_size, write_time + write_period * duty_cycle)

    expected_data = [new_data[i] if current_mask[i] else current_data[i] for i in range(word_size)]
    settling_time = write_period + write_settling_time
    actual_data = get_address_data(write_address, write_time + settling_time)

    debug_error("Write failure: At time {:.3g} address {}".format(write_time, write_address),
                expected_data, actual_data)


def verify_read_event(read_event):
    read_time = read_event[0]
    read_address = read_event[1]
    read_period = read_event[2]

    expected_data = get_address_data(read_address, read_time)
    settling_time = read_period + read_settling_time
    out_pattern = data_pattern
    actual_data = sim_data.get_bus_binary(out_pattern, word_size, read_time + settling_time)

    debug_error("Read failure: At time {:.3g} address {}".format(read_time, read_address), expected_data, actual_data)


def debug_error(comment, expected_data, actual_data):
    equal_vec = np.equal(actual_data, expected_data)
    if not np.all(equal_vec):
        wrong_bits = [(len(actual_data) - 1 - x) for x in
                      np.nonzero(np.invert(equal_vec))[0]]
        print("{} btw bits {}, {} \n expected \t {}\n found    \t {}".
              format(comment, wrong_bits[0], wrong_bits[-1],
                     list(expected_data), list(actual_data)))


def vector_to_int(vec):
    return int("".join(map(str, vec)), 2)


def address_to_int(vec_str):
    return vector_to_int(vec_str.replace(",", "").replace(" ", ""))


def int_to_vec(int_):
    str_format = "0{}b".format(word_size + 1)
    return list(map(int, [x for x in format(int_, str_format)]))


def get_word(index, vec):
    index = num_words - index - 1
    return vec[index * word_size:(1 + index) * word_size]


def ref_to_bus_delay(ref_edge_type, pattern, start_time, end_time, num_bits=1,
                     bit=0, edgetype2=None):
    if edgetype2 is None:
        edgetype2 = sim_data.EITHER_EDGE

    def internal_delay(signal):
        return sim_data.get_delay(clk_reference, signal, start_time, start_time, end_time,
                                  edgetype1=ref_edge_type, edgetype2=edgetype2,
                                  edge1=sim_data.FIRST_EDGE, edge2=sim_data.LAST_EDGE,
                                  num_bits=1, bit=bit)

    if num_bits == 1 and bit >= 0:
        return internal_delay(pattern.format(bit))
    else:
        results = []
        if num_bits < 0:
            num_bits = word_size
        for i in range(num_bits):
            if pattern.format(i) in all_saved_list:
                results.append(internal_delay(pattern.format(i)))
        return list(reversed(results))


def clk_bar_to_bus_delay(pattern, start_time, end_time, num_bits=-1, bit=0, edgetype2=None):
    return ref_to_bus_delay(sim_data.FALLING_EDGE, pattern, start_time, end_time, num_bits, bit,
                            edgetype2=edgetype2)


def pattern_from_saved(pattern, *args):
    pattern = re.search(pattern, all_saved_signals)
    if pattern is None:
        return ""
    pattern = pattern.group(0)
    for i in range(0, len(args), 2):
        pattern = re.sub(args[i], args[i + 1], pattern)
    pattern = re.sub("Xbank[01]+", "Xbank{0}", pattern)
    return pattern


arg_parser = create_arg_parser()
arg_parser.add_argument("-v", "--verbose", action="count", default=0)
mode, options = parse_options(arg_parser)
openram_temp = get_sim_directory(options, mode)

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
read_settling_time = 120e-12
write_settling_time = 150e-12

logging.info("Simulation Dir = {}".format(openram_temp))

stim_file = os.path.join(openram_temp, "stim.sp")
meas_file = os.path.join(openram_temp, "stim.measure")
sim_file = os.path.join(openram_temp, "tran.tran.tran")
states_file = os.path.join(openram_temp, "state_probes.json")
logging.info("Simulation end: " + time.ctime(os.path.getmtime(sim_file)))

sim_data = PsfReader(sim_file)
sim_data.thresh = 0.45

all_saved_signals = "\n".join(sim_data.get_signal_names())
all_saved_list = list(sim_data.get_signal_names())

meas_str = open(meas_file, 'r').read()
stim_str = open(stim_file, 'r').read()

with open(states_file, "r") as states_file_:
    state_probes = json.load(states_file_)

setup_time = 0.015e-9

mask_pattern = "mask[{}]"

if not schematic:
    wordline_pattern = pattern_from_saved("v\(\S+wl\S+Xbitcell_array\S+\)", "wl\[[0-9]+\]", "wl[{1}]",
                                          "r[0-9]+", "r{1}")
    wordline_en_pattern = pattern_from_saved("v\(\S+wordline_en\S+Xwordline_driver\S+\)")
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

write_driver_in_pattern = pattern_from_saved("v\(\S+data_in\S+Xdriver\S+\)", "Xdriver_[0-9]+", "Xdriver_{1}",
                                             "\[[0-9]+\]", "[{1}]")

address_pattern = "A[{}]"

probe_cols_str = search_file(stim_file, r"Probe cols = \[(.*)\]")
probe_cols = list(map(int, probe_cols_str.split(",")))
probe_bits = [int(x / words_per_row) for x in probe_cols]

if __name__ == "__main__":

    clk_reference = "v(" + re.search(r".meas tran {}.* TRIG v\((\S+)\) VAL".
                                     format("PRECHARGE"), stim_str).group(1) + ")"

    area = float(search_file(stim_file, r"Area=([0-9\.]+)um2"))

    all_read_events = []
    all_write_events = []

    test_events = search_file(stim_file, "-- Address Test:.*\[(.*)\]")
    for test_event in test_events:
        split_str = test_event.split(",")

        addr, row, col_index, bank = [int(x) for x in split_str[:4]]
        event_time, read_period, write_period, read_duty, write_duty = [float(x) for x in split_str[4:]]

        read_events = [event_time + write_period, event_time + 3 * write_period + read_period]
        write_events = [event_time + write_period + read_period]

        for read_time in read_events:
            all_read_events.append((read_time * 1e-9, addr, read_period * 1e-9, read_duty, row, col_index, bank))

        for write_time in write_events:
            all_write_events.append((write_time * 1e-9, addr, write_period * 1e-9, write_duty, row, col_index, bank))

    # Precharge and Decoder delay
    max_decoder_delay = 0
    max_precharge = 0
    for event in all_read_events + all_write_events:
        max_dec_, dec_delays = measure_delay_from_stim_measure("decoder", event)
        max_decoder_delay = max(max_decoder_delay, max_dec_)

        max_prech_, prech_delays = measure_delay_from_stim_measure("precharge_delay", event)
        max_precharge = max(max_precharge, max_prech_)

    print("\nDecoder delay = {:.2f}p".format(max_decoder_delay / 1e-12))
    print("Precharge delay = {:.2f}p".format(max_precharge / 1e-12))

    # Analyze Reads

    print("----------------Read Analysis---------------")
    for read_event in all_read_events:
        verify_read_event(read_event)

    max_dout = 0
    max_read_event = all_read_events[-1]
    max_read_bit_delays = [0] * word_size
    for read_event in all_read_events:
        d_delays = clk_bar_to_bus_delay(data_pattern, read_event[0],
                                        read_event[0] + read_event[2] +
                                        read_settling_time, word_size)

        if max(d_delays) > max_dout:
            max_read_event = read_event
            max_dout = max(d_delays)
            max_read_bit_delays = d_delays

    print("clk_bar to Read bus out delay = {:.2f}p".format(max_dout / 1e-12))

    total_read = max(max_precharge, max_decoder_delay) + max_dout
    print("Total Read delay = {:.2f}p".format(total_read / 1e-12))

    read_energies = [measure_energy(x[0], x[2]) for x in all_read_events]

    print("Max read energy = {:.2f} pJ".format(max(read_energies) / 1e-12))

    # analyze writes
    print("----------------Write Analysis---------------")

    for write_event_ in all_write_events:
        verify_write_event(write_event_)

    write_energies = [measure_energy(x[0], x[2]) for x in all_write_events]

    # Write delay
    max_q_delay = 0
    max_write_event = all_write_events[-1]
    max_write_bit_delays = [0] * word_size
    for write_event in all_write_events:
        max_valid_delay = (1 + write_event[3]) * write_event[2]
        max_q_, q_delays = measure_delay_from_stim_measure("state_delay", write_event,
                                                           max_delay=max_valid_delay)
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
            return clk_bar_to_bus_delay(net, start_time, end_time, num_bits=1, edgetype2=edge)


        def print_max_delay(desc, val):
            if val > 0:
                print("{} delay = {:.3g}p".format(desc, val * 1e12))


        # write analysis:
        if verbose_save:
            max_write_bit = (word_size - 1) - np.argmax(max_write_bit_delays)
        else:
            max_write_bit = max(probe_bits)

        write_address = max_write_event[1]
        write_period = max_write_event[2]
        write_start_time = max_write_event[0]
        max_write_row = max_write_event[4]
        write_bank = max_write_event[6]
        write_end_time = write_start_time + write_period + write_settling_time

        q_net = "v({})".format(state_probes[str(write_address)][max_write_bit])

        max_write_col = int(re.search("r[0-9]+_c([0-9]+)_", q_net).group(1))

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

        print("\nRead Critical Path: t = {:.3g}n\n".format(max_read_event[0]))

        # Read analysis

        if verbose_save:
            max_read_bit = (word_size - 1) - np.argmax(max_read_bit_delays)
        else:
            max_read_bit = max(probe_bits)

        max_read_address = max_read_event[1]
        max_read_row = max_read_event[4]
        max_read_period = max_read_event[2]
        read_start_time = max_read_event[0]
        read_end_time = read_start_time + max_read_period + read_settling_time
        read_bank = max_read_event[6]

        read_q_net = "v({})".format(state_probes[str(max_read_address)][max_read_bit])

        max_read_col = int(re.search("r[0-9]+_c([0-9]+)_", read_q_net).group(1))

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
            bl_plot_pattern = bl_pattern if bl_delay > br_delay else br_pattern
        else:
            bl_delay = get_max_pattern_delay(bl_out_pattern, max_read_bit)
            br_delay = get_max_pattern_delay(br_out_pattern, max_read_bit)
            bl_plot_pattern = bl_out_pattern if bl_delay > br_delay else br_out_pattern

        and_out_delay = get_max_pattern_delay(and_out_pattern, max_read_bit)

        print_max_delay("Wordline EN", wordline_en_delay)
        print_max_delay("Wordline ", wordline_delay)
        print_max_delay("Sample Fall", sample_fall_delay)
        print_max_delay("Sample Rise", sample_rise_delay)
        print_max_delay("Sense EN", sense_en_delay)
        print_max_delay("BL", bl_delay)
        print_max_delay("BR", br_delay)
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
            else:
                bit = max_read_bit
                col = max_read_col
                start_time = read_start_time
                end_time = read_end_time
                q_net = read_q_net
                row = max_read_row
                bank = read_bank

            plt.plot(*sim_data.get_signal_time(clk_reference, from_t=start_time, to_t=end_time), label="clk_buf")

            if options.plot == "write":
                plt.plot(*sim_data.get_signal_time(write_en_pattern.format(bank, max_write_bit),
                                                   from_t=start_time, to_t=end_time), label="write_en")
                plt.plot(*sim_data.get_signal_time(write_en_bar_pattern.format(bank, max_write_bit),
                                                   from_t=start_time, to_t=end_time), label="write_en_bar")
                if verbose_save:
                    plt.plot(*sim_data.get_signal_time(flop_clk_in_pattern.format(bank, max_write_bit),
                                                       from_t=start_time, to_t=end_time), label="flop_clk")
                    plt.plot(*sim_data.get_signal_time(write_driver_in_pattern.format(bank, max_write_bit),
                                                       from_t=start_time, to_t=end_time), label="flop_out")
                plt.plot(*sim_data.get_signal_time(bl_pattern.format(bank, max_write_col),
                                                   from_t=start_time, to_t=end_time), label="bl")
                plt.plot(*sim_data.get_signal_time(br_pattern.format(bank, max_write_col),
                                                   from_t=start_time, to_t=end_time), label="br")
            else:
                plt.plot(*sim_data.get_signal_time(sample_en_bar_pattern.format(bank, max_read_bit),
                                                   from_t=start_time, to_t=end_time), label="sample")
                plt.plot(*sim_data.get_signal_time(sense_en_pattern.format(bank, max_read_bit),
                                                   from_t=start_time, to_t=end_time), label="sense_en")
                plt.plot(*sim_data.get_signal_time(bl_plot_pattern.format(bank, max_read_bit),
                                                   from_t=start_time, to_t=end_time), label="bitline")
                plt.plot(*sim_data.get_signal_time(and_out_pattern.format(bank, max_read_bit),
                                                   from_t=start_time, to_t=end_time), label="and_out")
            plt.plot(*sim_data.get_signal_time(wordline_pattern.format(bank, row),
                                               from_t=start_time, to_t=end_time),
                     label="wl[{}]".format(row))
            plt.plot(*sim_data.get_signal_time(q_net, from_t=start_time, to_t=end_time), label="Q")
            plt.axhline(y=0.45, linestyle='--', linewidth=0.5)
            plt.grid()
            plt.legend(loc="center left", fontsize="x-small")
            plt.show()
