import os
import re
import sys

import numpy as np

script_dir = os.path.dirname(__file__)
sys.path.append(os.path.join(script_dir, ".."))

import debug
from psf_reader import PsfReader


# TestBase.initialize_tests("config_bl_{}")
num_cols = num_rows = word_size = 64
sim_dir = stim_file = meas_file = ""
sim_data = None  # type: PsfReader
all_saved_signals = ""
meas_str = ""
stim_str = ""
period = 1
duty_cycle = 0.5

clk_reference = "clk"
data_flop_in_pattern = data_pattern = "data[{}]"
mask_pattern = "mask[{}]"
dout_pattern = "data[{}]"

digit_regex = "([0-9\.]+)"


def setup(num_cols_, num_rows_, sim_dir_):
    global num_cols, num_rows, sim_dir, sim_data, all_saved_signals, meas_str, stim_str
    global stim_file, meas_file
    num_cols = num_cols_
    num_rows = num_rows_
    sim_dir = sim_dir_

    stim_file = os.path.join(sim_dir, "stim.sp")
    meas_file = os.path.join(sim_dir, "stim.measure")
    sim_file = os.path.join(sim_dir, 'transient1.tran.tran')

    sim_data = PsfReader(sim_file)

    all_saved_signals = "\n".join(sim_data.get_signal_names())

    meas_str = open(meas_file, 'r').read()
    stim_str = open(stim_file, 'r').read()


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


def measure_energy(times):
    if isinstance(times, str):
        times = float(times) * 1e-9
    if isinstance(times, float):
        times = (times, times + period)
    current = sim_data.get_signal('Vvdd:p', times[0], times[1])
    time = sim_data.slice_array(sim_data.time, times[0], times[1])
    power = -np.trapz(current, time) * 0.9

    return power


def measure_delay_from_meas(pattern, max_delay=None):
    if max_delay is None:
        max_delay = (1 + duty_cycle) * period
    delays = [float(x) for x in pattern.findall(meas_str)]

    valid_delays = list(filter(lambda x: x < max_delay, delays))

    max_delay = max(valid_delays)
    return max_delay, valid_delays


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


def standardize_pattern(pattern, specific_loc="\[[0-9]+\]", gen_loc="[{0}]"):
    pattern = "v(" + pattern + ")"
    pattern = re.sub(specific_loc, gen_loc, pattern)
    return pattern


def get_q_pattern(write_address):
    specific_q_pattern = "v(" + extract_probe_pattern("STATE_DELAY") + ")"
    if re.search("_r[0-9]+_c[0-9]+", specific_q_pattern):
        specific_index = re.search("_r[0-9]+_c[0-9]+", specific_q_pattern).group()
        return specific_q_pattern.replace(specific_index, "_r{}".format(write_address) + "_c{0}")
    else:
        specific_index = re.search("_c[0-9]+_r[0-9]+", specific_q_pattern).group()
        return specific_q_pattern.replace(specific_index, "_c{0}" + "_r{0}".format(write_address))


def get_address_data(address, time):
    q_pattern = get_q_pattern(address)
    return sim_data.get_bus_binary(q_pattern, num_cols, time)


def verify_write_event(write_time, write_address, negate=False):
    write_time = float(write_time) * 1e-9

    current_data = get_address_data(write_address, write_time)
    current_mask = sim_data.get_bus_binary(mask_pattern, num_cols, write_time)

    new_data = sim_data.get_bus_binary(data_pattern, num_cols, write_time + period*duty_cycle)

    expected_data = [new_data[i] if current_mask[i] else current_data[i] for i in range(num_cols)]
    settling_time = (1 + duty_cycle) * period
    actual_data = get_address_data(write_address, write_time + settling_time)
    if negate:
        actual_data = [int(not x) for x in actual_data]

    debug_error("Write failure: At time {:.3g} address {}".format(write_time, write_address),
                expected_data, actual_data)


def measure_read_delays(read_time):
    reference_time = read_time + duty_cycle * period
    stop_time = read_time + period
    measured_delays = [sim_data.get_delay(clk_reference, data_flop_in_pattern.format(col),
                                          t1=reference_time, t2=reference_time, stop_time=stop_time,
                                          edgetype1=sim_data.FALLING_EDGE, edge1=sim_data.FIRST_EDGE,
                                          edge2=sim_data.LAST_EDGE) for col in range(num_cols)]
    return list(filter(lambda x: x < np.inf, measured_delays))


def debug_error(comment, expected_data, actual_data):
    if not np.all(np.equal(actual_data, expected_data)):
        debug.error("{} \n expected \t {}\n found    \t {}".
                    format(comment, list(expected_data), list(actual_data)), 0)


def vector_to_int(vec):
    return int("".join(map(str, vec)), 2)


def int_to_vec(int_):
    str_format = "0{}b".format(word_size + 1)
    return list(map(int, [x for x in format(int_, str_format)]))


def get_word(index, vec):
    return vec[index * word_size:(1 + index) * word_size]


def clk_to_bus_delay(pattern, start_time, end_time, num_bits=1):
    return sim_data.get_delay(clk_reference, pattern, start_time, start_time,
                              end_time, edgetype1=sim_data.RISING_EDGE, edgetype2=sim_data.EITHER_EDGE,
                              edge1=sim_data.FIRST_EDGE, edge2=sim_data.LAST_EDGE, num_bits=num_bits)


def clk_bar_to_bus_delay(pattern, start_time, end_time, num_bits=1):
    return sim_data.get_delay(clk_reference, pattern, start_time, start_time,
                              end_time, edgetype1=sim_data.FALLING_EDGE, edgetype2=sim_data.EITHER_EDGE,
                              edge1=sim_data.FIRST_EDGE, edge2=sim_data.LAST_EDGE, num_bits=num_bits)


def pattern_from_saved(pattern, *args):
    pattern = re.findall(pattern, all_saved_signals)[0]
    for i in range(0, len(args), 2):
        pattern = re.sub(args[i], args[i + 1], pattern)
    return pattern
