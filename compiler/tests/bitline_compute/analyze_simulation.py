#!/bin/env python
import os
import re
import sys

sys.path.append("../..")
sys.path.append("..")

import numpy as np
from matplotlib import pyplot as plt

import debug
from psf_reader import PsfReader


# TestBase.initialize_tests("config_bl_{}")


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


def measure_delay(pattern, max_delay=None):
    if max_delay is None:
        max_delay = (1 + duty_cycle) * period
    delays = [float(x) for x in pattern.findall(meas_str)]

    valid_delays = list(filter(lambda x: x < max_delay, delays))

    max_delay = max(valid_delays)
    return max_delay, valid_delays


def extract_probe_pattern(meas_name):
    sample = re.search(".meas tran {}.* TARG v\((.+)\) VAL".format(meas_name), stim_str).group(1)
    specific_index = re.search("\[[0-9]+\]", sample)
    if specific_index is None:
        return sample
    generic_pattern = sample.replace(specific_index.group(), "[{0}]")
    return generic_pattern


def standardize_pattern(pattern, specific_loc="", gen_loc=""):
    pattern = "v(" + pattern + ")"
    pattern = re.sub(specific_loc, gen_loc, pattern)
    return pattern


def get_q_pattern(write_address):
    specific_q_pattern = "v(" + extract_probe_pattern("STATE_DELAY") + ")"
    specific_index = re.search("_r[0-9]+_c[0-9]+", specific_q_pattern).group()
    q_pattern = specific_q_pattern.replace(specific_index, "_r{}".format(write_address) + "_c{0}")
    return q_pattern


def get_address_data(address, time):
    q_pattern = get_q_pattern(address)
    return sim_data.get_bus_binary(q_pattern, num_cols, time)


def verify_write_event(write_time, write_address):
    write_time = float(write_time) * 1e-9

    current_data = get_address_data(write_address, write_time)
    current_mask = sim_data.get_bus_binary(mask_pattern, num_cols, write_time)

    new_data = sim_data.get_bus_binary(data_pattern, num_cols, write_time)

    expected_data = [new_data[i] if current_mask[i] else current_data[i] for i in range(num_cols)]
    settling_time = (1 + duty_cycle) * period
    actual_data = get_address_data(write_address, write_time + settling_time)

    if not np.array_equal(actual_data, expected_data):
        debug.error("Read failure: At time {:.3g} \n expected \t {}\n found    \t {}".
                    format(write_time, expected_data, actual_data), 0)


def verify_read_event(read_time, read_address):
    read_time = float(read_time) * 1e-9
    sel_and = sim_data.get_binary("s_and", read_time)
    if not sel_and[0]:
        return
    expected_data = get_address_data(read_address, read_time)
    settling_time = period
    actual_data = sim_data.get_bus_binary(data_flop_in_pattern, num_cols, read_time + settling_time)

    debug_error("Read failure: At time {:.3g} address {}".format(read_time, read_address), expected_data, actual_data)


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


def verify_bitline_event(time, addr0, addr1):
    compute_time = float(time) * 1e-9
    initial_d1 = get_address_data(addr0, compute_time)
    initial_d2 = get_address_data(addr1, compute_time)

    # verify and and nor calculated correctly
    expected_and = [d1 & d2 for d1, d2 in zip(initial_d1, initial_d2)]
    expected_nor = [int(not (d1 | d2)) for d1, d2 in zip(initial_d1, initial_d2)]

    cycle_end = compute_time + period

    actual_and = sim_data.get_bus_binary(and_pattern, num_cols, cycle_end)
    actual_nor = sim_data.get_bus_binary(nor_pattern, num_cols, cycle_end)

    debug_error("AND failure at time {:.3g}".format(compute_time), expected_and, actual_and)
    debug_error("NOR failure at time {:.3g}".format(compute_time), expected_nor, actual_nor)

    # verify data was not over-writtten
    new_d1 = get_address_data(addr0, cycle_end)
    debug_error("Address {} overwritten".format(addr0), initial_d1, new_d1)
    new_d2 = get_address_data(addr1, cycle_end)
    debug_error("Address {} overwritten".format(addr1), initial_d2, new_d2)

    # verify sum and carry
    cin = sim_data.get_bus_binary(cin_pattern, num_words, cycle_end)

    sum_end = cycle_end + duty_cycle * period

    # cout = sim_data.get_bus_binary(cout_pattern, num_words, sum_end)
    flop_din = sim_data.get_bus_binary(data_flop_in_pattern, num_cols, sum_end)

    write_address = vector_to_int(sim_data.get_bus_binary(address_pattern, address_width, cycle_end))
    actual_mask_bar = sim_data.get_bus_binary(mask_in_bar_pattern, num_cols, sum_end)
    previous_data = get_address_data(write_address, compute_time)
    actual_data = get_address_data(write_address, compute_time + 2 * period)

    for word in range(num_words):
        d1 = vector_to_int(get_word(word, initial_d1))
        d2 = vector_to_int(get_word(word, initial_d2))
        expected_sum_ = int_to_vec(d1 + d2 + cin[word])
        expected_carry = expected_sum_[0]
        expected_sum = expected_sum_[1:]

        actual_sum = get_word(word, flop_din)
        # actual_carry = cout[word]

        debug_error("Incorrect sum at time {} ".format(compute_time), expected_sum, actual_sum)
        # debug_error("Incorrect carry at time {} ".format(compute_time), expected_carry, actual_carry)

        # verify write back

        expected_data = [get_word(word, previous_data)[i] if get_word(word, actual_mask_bar)[i]
                         else expected_sum[i] for i in range(word_size)]
        written_data = get_word(word, actual_data)

        debug_error("Write-back to {} unsuccessful at time {} ".format(write_address, compute_time),
                    expected_data, written_data)


def measure_bitline_delays(bitline_time):
    reference_time = bitline_time + duty_cycle * period
    stop_time = bitline_time + (1 + duty_cycle) * period
    measured_delays = [sim_data.get_delay(clk_reference, data_flop_in_pattern.format(col),
                                          t1=reference_time, t2=reference_time, stop_time=stop_time,
                                          edgetype1=sim_data.FALLING_EDGE, edge1=sim_data.FIRST_EDGE,
                                          edge2=sim_data.LAST_EDGE) for col in range(num_cols)]
    return list(filter(lambda x: x < np.inf, measured_delays))


def clk_to_bus_delay(pattern, start_time, end_time, num_bits=1):
    return sim_data.get_delay(clk_reference, pattern, start_time, start_time,
                              end_time, edgetype1=sim_data.RISING_EDGE, edgetype2=sim_data.EITHER_EDGE,
                              edge1=sim_data.FIRST_EDGE, edge2=sim_data.LAST_EDGE, num_bits=num_bits)


def clk_bar_to_bus_delay(pattern, start_time, end_time, num_bits=1):
    return sim_data.get_delay(clk_reference, pattern, start_time, start_time,
                              end_time, edgetype1=sim_data.FALLING_EDGE, edgetype2=sim_data.EITHER_EDGE,
                              edge1=sim_data.FIRST_EDGE, edge2=sim_data.LAST_EDGE, num_bits=num_bits)


def print_max_timing(all_times, comment):
    max_col = 0
    max_time = 0
    event_time = 0
    for i in range(len(all_writes)):
        current_delays = [all_times[i][j] if all_times[i][j] < np.inf else 0 for j in range(len(all_times[i]))]
        if np.max(current_delays) > max_time:
            max_time = np.max(current_delays)
            max_col = num_cols - np.argmax(current_delays)
            event_time = all_writes[i][0]

    print(comment, "event time = {:.2f} ns".format(event_time * 1e9))
    print("\t\t\t\t\t\tmax value = {:.2f} ps ".format(max_time * 1e12))
    print("\t\tmax-col = {}".format(max_col))


def pattern_from_saved(pattern, *args):
    pattern = re.findall(pattern, all_saved_signals)[0]
    for i in range(0, len(args), 2):
        pattern = re.sub(args[i], args[i + 1], pattern)
    return pattern


baseline = False
word_size = 32
num_cols = 256
num_rows = 128
fixed = True

num_words = int(num_cols / word_size)
address_width = int(np.log2(num_rows))

folder_name = "baseline" if baseline else "compute"
openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "bl_sram")
fixed_str = "_fixed" if fixed else ""
temp_folder = os.path.join(openram_temp, "{}_{}_{}{}".format(folder_name, num_cols, num_rows, fixed_str))

sim_dir = temp_folder

debug.info(1, "Simulation Dir = {}".format(sim_dir))

stim_file = os.path.join(sim_dir, "stim.sp")
meas_file = os.path.join(sim_dir, "stim.measure")
sim_file = os.path.join(sim_dir, 'transient1.tran.tran')

sim_data = PsfReader(sim_file)

all_saved_signals = "\n".join(sim_data.get_signal_names())

meas_str = open(meas_file, 'r').read()
stim_str = open(stim_file, 'r').read()

setup_time = 0.015e-9

mask_in_bar_pattern = standardize_pattern(extract_probe_pattern("mask_col"), "Xdriver_[0-9]+", "Xdriver_{0}")

mask_pattern = "mask[{}]"
data_flop_in_pattern = standardize_pattern(extract_probe_pattern("READ_DELAY"), "dff[0-9]+", "dff{0}")

write_en_pattern = pattern_from_saved("v\(\S+write_en(?!_bar)\S+Xdriver\S+\)", "Xdriver_[0-9]+", "Xdriver_{0}")

write_en_bar_pattern = pattern_from_saved("v\(\S+write_en_bar\S+Xdriver\S+\)", "Xdriver_[0-9]+", "Xdriver_{0}")

write_driver_in_pattern = pattern_from_saved("v\(\S+data_in\S+Xdriver\S+\)", "Xdriver_[0-9]+", "Xdriver_{0}",
                                             "\[[0-9]+\]", "[{0}]")

bl_pattern = pattern_from_saved("v\(\S+bl\S+Xbitcell\S+\)", "c[0-9]+", "c{0}", "\[[0-9]+\]", "[{0}]")
br_pattern = pattern_from_saved("v\(\S+br\S+Xbitcell\S+\)", "c[0-9]+", "c{0}", "\[[0-9]+\]", "[{0}]")

flop_clk_in_pattern = pattern_from_saved("v\(\S+clk_bar\S+Xdata_in\S+\)", "dff[0-9]+", "dff{0}")

data_pattern = "D[{}]"

flop_out_pattern = data_flop_in_pattern.replace("DATA", "data_in")

address_pattern = "A[{}]"

bus_out_pattern = "v(Xsram.Xalu.bus_out[{}])"

and_pattern = "and[{}]"
nor_pattern = "nor[{}]"
cin_pattern = "cin[{}]"
cout_pattern = "cout[{}]"

clk_reference = "v(" + re.search(".meas tran {}.* TRIG v\((\S+)\) VAL".format("PRECHARGE"), stim_str).group(1) + ")"

period = float(search_file(stim_file, "\* Period = ([0-9\.]+) ")) * 1e-9
duty_cycle = float(search_file(stim_file, "\* Duty Cycle = ([0-9\.]+) "))

area = float(search_file(stim_file, "Area=([0-9\.]+)um2"))

print("\nArea = {:2g} um2".format(area))
print("Period = {:2g} ns".format(period))
print("Duty Cycle = {:2g}\n".format(duty_cycle))

# Decoder delay
max_decoder_delay, _ = measure_delay(re.compile('decoder_a.*= (?P<delay>\S+)\s\n'), 0.9 * period)

# Precharge delay
max_precharge, _ = measure_delay(re.compile('precharge_delay.*= (?P<delay>\S+)\s\n'), 0.9 * period)

print("\nDecoder delay = {:.2f}p".format(max_decoder_delay / 1e-12))
print("Precharge delay = {:.2f}p".format(max_precharge / 1e-12))

# Read + write to SR
sr_time = 1e-9 * float(search_file(stim_file, "t = ([0-9\.]+) Shift-Register"))
sr_energy = measure_energy([sr_time - period, sr_time + period])

# analyze writes
print("----------------Write Analysis---------------")

write_events = search_file(stim_file, "t = ([0-9\.]+) Write .* \(([0-9]+)\)")
write_energies = [measure_energy(x[0]) for x in write_events]
for write_time_, write_address_ in write_events:
    verify_write_event(write_time_, write_address_)

# Write delay
max_q_delay, _ = measure_delay(re.compile('state_delay.*= (?P<delay>\S+)\s\n'))
print("Q state delay = {:.2f} ps".format(max_q_delay / 1e-12))

total_write = max(max_precharge, max_decoder_delay) + max_q_delay
print("Total Write delay = {:.2f} ps".format(total_write / 1e-12))
print("Max write energy = {:.2f} pJ".format(max(write_energies) / 1e-12))

# Reads
print("----------------Read Analysis---------------")
read_events = search_file(stim_file, "t = ([0-9\.]+) Read .* \(([0-9]+)\)")
for read_time_, read_address_ in read_events:
    verify_read_event(read_time_, read_address_)

read_delays = [measure_read_delays(1e-9 * float(x[0])) for x in read_events]

max_dout = np.max(read_delays)

print("clk_bar to Read bus out delay = {:.2f}p".format(max_dout / 1e-12))

total_read = max(max_precharge, max_decoder_delay) + max_dout
print("Total Read delay = {:.2f}p".format(total_read / 1e-12))

read_energies = [measure_energy(x[0]) for x in read_events]

print("Max read energy = {:.2f} pJ".format(max(read_energies) / 1e-12))

print("----------------Sum Analysis---------------")
bitline_events = search_file(stim_file, "t = ([0-9\.]+) Bitline \(([0-9]+)\) \+ \(([0-9]+)\) ")

for bitline_time_, addr0_, addr1_ in bitline_events:
    verify_bitline_event(bitline_time_, addr0_, addr1_)

# sum_delays = [measure_bitline_delays(1e-9*float(x[0])) for x in bitline_events]

bitline_times = [1e-9 * float(x[0]) for x in bitline_events]

sum_delays = [clk_bar_to_bus_delay(data_flop_in_pattern, x + duty_cycle * period,
                                   x + (1 + duty_cycle) * period, num_bits=num_cols)
              for x in bitline_times]

for i in range(len(sum_delays)):
    sum_delays[i] = [sum_delays[i][j] if sum_delays[i][j] < np.inf else 0 for j in range(len(sum_delays[i]))]

print("max clk_bar to data in flop delay (sum) = {:.2f}p".format(np.max(sum_delays) / 1e-12))

print("----------------Energy Analysis---------------")

# Read + write to SR
sr_time = 1e-9 * float(search_file(stim_file, "t = ([0-9\.]+) Shift-Register"))
sr_energy = measure_energy([sr_time - period, sr_time + period])
print("Read and Write to SR energy = {:.2f} pJ".format(sr_energy / 1e-12))

# Add + Write back
for action in ["MASK-IN", "MSB", "LSB"]:
    write_time = 1e-9 * float(search_file(stim_file, "t = ([0-9\.]+) Write-back {}".format(action)))
    energy = measure_energy([write_time - period, write_time + period])
    print("BL compute and write back using {} energy = {:.2f} pJ".format(action, energy / 1e-12))

print("----------------Critical Paths---------------")

print("\nWrite Critical Path")

# write:
write_events = search_file(stim_file, "t = ([0-9\.]+) Write .* \(([0-9]+)\)")
write_backs = search_file(stim_file, "t = ([0-9\.]+) Write-back .* \(([0-9]+)\)")
all_writes = write_events + write_backs

all_writes = [(1e-9 * float(x[0]), x[1]) for x in all_writes]

# find maximum write delay
max_all_write_address = max_all_write_delay = max_all_write_time = 0
max_clk_bar_to_q = None
for write_time_, write_address_ in all_writes:
    q_pattern = get_q_pattern(write_address_)
    clk_bar_to_q = clk_bar_to_bus_delay(q_pattern, write_time_, write_time_ + period, num_cols)
    if max(clk_bar_to_q) > max_all_write_delay:
        max_all_write_delay = max(clk_bar_to_q)
        max_all_write_address = write_address_
        max_all_write_time = write_time_
        max_clk_bar_to_q = clk_bar_to_q

max_write_col = (num_cols - 1) - np.argmax(max_clk_bar_to_q)

start_time = max_all_write_time + duty_cycle * period
end_time = max_all_write_time + period
write_en_delay = clk_bar_to_bus_delay(write_en_pattern.format(max_write_col), start_time, end_time)
write_en_bar_delay = clk_bar_to_bus_delay(write_en_bar_pattern.format(max_write_col), start_time, end_time)

data_out_delay = clk_bar_to_bus_delay(write_driver_in_pattern.format(max_write_col), start_time, end_time)

bl_delay = clk_bar_to_bus_delay(bl_pattern.format(max_write_col), start_time, end_time)
br_delay = clk_bar_to_bus_delay(br_pattern.format(max_write_col), start_time, end_time)
q_delay = clk_bar_to_bus_delay(get_q_pattern(max_all_write_address).format(max_write_col), start_time, end_time)

# Plots
end_time = start_time + 0.7*period

plt.plot(*sim_data.get_signal_time(clk_reference, from_t=start_time, to_t=end_time), label="clk_buf")
plt.plot(*sim_data.get_signal_time(write_en_pattern.format(max_write_col),
                                   from_t=start_time, to_t=end_time), label="write_en")
plt.plot(*sim_data.get_signal_time(write_en_bar_pattern.format(max_write_col),
                                   from_t=start_time, to_t=end_time), label="write_en_bar")
plt.plot(*sim_data.get_signal_time(flop_clk_in_pattern.format(max_write_col),
                                   from_t=start_time, to_t=end_time), label="flop_clk")
plt.plot(*sim_data.get_signal_time(write_driver_in_pattern.format(max_write_col),
                                   from_t=start_time, to_t=end_time), label="flop_out")
plt.plot(*sim_data.get_signal_time(bl_pattern.format(max_write_col),
                                   from_t=start_time, to_t=end_time), label="bl")
plt.plot(*sim_data.get_signal_time(get_q_pattern(max_all_write_address).format(max_write_col),
                                   from_t=start_time, to_t=end_time), label="Q")
plt.axhline(y=0.45, linestyle='--', linewidth=0.5)
plt.grid()
plt.legend(loc="center right", fontsize="x-small")
plt.show()
