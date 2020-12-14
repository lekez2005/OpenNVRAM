import os
import re
import sys

import numpy as np

script_dir = os.path.dirname(__file__)
sys.path.append(os.path.join(script_dir, ".."))

from psf_reader import PsfReader

# TestBase.initialize_tests("config_bl_{}")
num_cols = num_rows = word_size = 64
num_words = 1
sim_dir = stim_file = meas_file = ""
sim_data = None  # type: PsfReader
all_saved_signals = ""
all_saved_list = []
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
    global stim_file, meas_file, all_saved_list
    num_cols = num_cols_
    num_rows = num_rows_
    sim_dir = sim_dir_

    stim_file = os.path.join(sim_dir, "stim.sp")
    meas_file = os.path.join(sim_dir, "stim.measure")
    sim_file = os.path.join(sim_dir, 'tran.tran.tran')

    sim_data = PsfReader(sim_file)

    all_saved_list = list(sim_data.get_signal_names())
    all_saved_signals = "\n".join(sorted(sim_data.get_signal_names()))

    if os.path.exists(meas_file):
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


def measure_delay_from_stim_measure(prefix, max_delay=None, event_time=None, index_pattern=""):
    if event_time is not None:
        time_suffix = "t{:.2g}".format(event_time * 1e9).replace('.', '_')
    else:
        time_suffix = ""

    pattern_str = r'{}_{}.*{}'.format(prefix, index_pattern, time_suffix) + " = (?P<delay>\S+)\s\n"

    pattern = re.compile(pattern_str)

    if index_pattern:
        bit_delays = [(int(x), float(y)) for x, y in pattern.findall(meas_str)]
        delays = [0] * len(bit_delays)
        for bit_, delay_ in bit_delays:
            delays[bit_] = delay_
        delays = list(reversed(delays))
    else:
        delays = [float(x) for x in pattern.findall(meas_str)]

    if max_delay is None:
        max_delay = np.inf
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


def get_address_data(address, time, state_probes, threshold):
    address_probes = list(reversed(state_probes[str(address)]))
    address_probes = ["v({})".format(x) for x in address_probes]

    address_data = [sim_data.get_signal(x, time)[0] > threshold for x in address_probes]
    address_data = [int(x) for x in address_data]
    return address_data


def verify_write_event(write_time, write_address, write_period, write_duty, negate=False):
    current_data = get_address_data(write_address, write_time)
    current_mask = sim_data.get_bus_binary(mask_pattern, word_size, write_time)

    new_data = sim_data.get_bus_binary(data_pattern, word_size, write_time +
                                       write_period * write_duty)

    expected_data = [0] * word_size
    for i in range(word_size):
        if current_mask[i]:
            if negate:
                expected_data[i] = int(not new_data[i])
            else:
                expected_data[i] = new_data[i]
        else:
            expected_data[i] = current_data[i]
    settling_time = write_period
    actual_data = get_address_data(write_address, write_time + settling_time)

    debug_error("Write failure: At time {:.3g} address {}".format(write_time, write_address),
                expected_data, actual_data)


def verify_read_event(read_time, read_address, read_period, read_duty, negate=False):
    # return
    expected_data = get_address_data(read_address, read_time + read_duty * read_period)
    settling_time = read_period
    out_pattern = data_pattern
    actual_data = sim_data.get_bus_binary(out_pattern, word_size, read_time + settling_time)

    if negate:
        actual_data = [int(not x) for x in actual_data]

    debug_error("Read failure: At time {:.3g} address {}".format(read_time, read_address), expected_data, actual_data)


def measure_read_delays(read_time, read_duty):
    reference_time = read_time + read_duty * period
    stop_time = read_time + period
    measured_delays = [sim_data.get_delay(clk_reference, data_flop_in_pattern.format(col),
                                          t1=reference_time, t2=reference_time, stop_time=stop_time,
                                          edgetype1=sim_data.FALLING_EDGE, edge1=sim_data.FIRST_EDGE,
                                          edge2=sim_data.LAST_EDGE) for col in range(num_cols)]
    return list(filter(lambda x: x < np.inf, measured_delays))


def debug_error(comment, expected_data, actual_data):
    equal_vec = np.equal(actual_data, expected_data)
    if not np.all(equal_vec):
        wrong_bits = [(len(actual_data) - 1 - x) for x in
                      np.nonzero(np.invert(equal_vec))[0]]
        print("{} btw bits {}, {}".format(comment, wrong_bits[0], wrong_bits[-1]))
        print_data = [list(reversed(range(len(actual_data)))), expected_data, actual_data]
        print_comments = ["", "expected", "actual"]

        widths = [len(str(x)) for x in print_data[0]]
        str_formats = ["{:<" + str(x) + "}" for x in widths]

        for i in range(3):
            print("{:<10}: \t[{}]".
                  format(print_comments[i],
                         " ".join([str_formats[j].format(print_data[i][j]) for j in
                                   range(len(actual_data))])))


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


def ref_to_bus_delay(ref_edge_type, pattern, start_time, end_time, num_bits=-1,
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


def clk_to_bus_delay(pattern, start_time, end_time, num_bits=-1, bit=0, edgetype2=None):
    return ref_to_bus_delay(sim_data.RISING_EDGE, pattern, start_time, end_time, num_bits, bit,
                            edgetype2=edgetype2)


def pattern_from_saved(pattern, *args):
    pattern = re.findall(pattern, all_saved_signals)[0]
    for i in range(0, len(args), 2):
        pattern = re.sub(args[i], args[i + 1], pattern)
    return pattern
