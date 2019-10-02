#!/bin/env python
import os
import re
import sys
sys.path.append("../..")
sys.path.append("..")

import numpy as np

import debug
from psf_reader import PsfReader

# TestBase.initialize_tests("config_bl_{}")

baseline = False
separate_vdd = False
word_size = 128
num_words = 128

folder_name = "baseline" if baseline else "compute"
openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "bl_sram")
temp_folder = os.path.join(openram_temp, "{}_{}_{}".format(folder_name, word_size, num_words))

sim_dir = temp_folder

debug.info(1, "Temp Dir = {}".format(sim_dir))


def search_file(filename, pattern):
    with open(filename, 'r') as file:
        content = file.read()
        match = re.search(pattern, content)
        return match.group(1)


stim_file = os.path.join(sim_dir, "stim.sp")
meas_file = os.path.join(sim_dir, "stim.measure")
sim_file = os.path.join(sim_dir, 'transient1.tran.tran')

read_period = float(search_file(stim_file, "for read period = ([0-9\.]+)n,"))*1e-9
write_period = float(search_file(stim_file, ", write period = ([0-9\.]+)n"))*1e-9

read_duty = float(search_file(stim_file, "read duty = ([0-9\.]+)n"))
write_duty = float(search_file(stim_file, "write duty = ([0-9\.]+)n"))

area = float(search_file(stim_file, "Area=([0-9\.]+)um2"))

print("\nArea = {} um2".format(area))

setup_time = 0.015e-9

sim_data = PsfReader(sim_file)

with open(meas_file, 'r') as f:
    meas_str = f.read()
with open(stim_file, 'r') as f:
    spice_str = f.read()

def get_command(label):
    command_pattern = re.compile('meas tran {}.*TD=(?P<start_time>\S+)n.*TD=(?P<end_time>\S+)n'.format(label),
                                 re.IGNORECASE)
    result = command_pattern.search(spice_str)
    return result


def measure_energy(times, verbose=True):
    total_power = 0
    vdd_names = ["vdd_buffers", "vdd_wordline", "vdd_data_flops", "vdd"] if separate_vdd else ["vdd"]
    for net in vdd_names:
        current = sim_data.get_signal('V{}:p'.format(net), times[0], times[1])
        time = sim_data.slice_array(sim_data.time, times[0], times[1])
        power = -np.trapz(current, time)*0.9
        total_power += power
        if verbose and separate_vdd:
            print("{} energy = {}".format(net, power))
    print()
    return total_power

def measure_delay(pattern, max_period):
    delays = [float(x) for x in pattern.findall(meas_str)]

    valid_delays = list(filter(lambda x: x < max_period, delays))

    max_delay = max(valid_delays)
    return max_delay, valid_delays


# Decoder delay
max_decoder_delay, _ = measure_delay(re.compile('decoder_a.*= (?P<delay>\S+)\s\n'), 0.9 * write_period)
print("\nDecoder delay = {:.2f}p".format(max_decoder_delay/1e-12))

# Precharge delay
max_precharge, _ = measure_delay(re.compile('precharge_delay.*= (?P<delay>\S+)\s\n'), 0.9 * read_period)
print("Precharge delay = {:.2f}p".format(max_precharge/1e-12))

# Read delay
max_tri_state, _ = measure_delay(re.compile('read_delay.*= (?P<delay>\S+)\s\n'), 0.9 * read_period)
print("\nTri-state delay = {:.2f}p".format(max_tri_state/1e-12))
total_read = max(max_precharge, max_decoder_delay) + max_tri_state
print("Total Read delay = {:.2f}p".format(total_read/1e-12))

# Write delay
max_q_delay, _ = measure_delay(re.compile('state_delay.*= (?P<delay>\S+)\s\n'), 0.9 * read_period)
print("\nQ state delay = {:.2f}p".format(max_q_delay/1e-12))
total_write = max(max_precharge, max_decoder_delay) + max_q_delay
print("Total Write delay = {:.2f}p".format(total_write/1e-12))

max_nor = max_and = 0

if not baseline:
    # AND delay
    max_and, _ = measure_delay(re.compile('and_delay.*= (?P<delay>\S+)\s\n'), 0.9 * read_period)
    print("\nAND delay = {:.2f}p".format(max_and / 1e-12))
    total_and = max(max_precharge, max_decoder_delay) + max_and
    print("Total AND delay = {:.2f}p".format(total_and / 1e-12))

    # NOR delay
    max_nor, _ = measure_delay(re.compile('nor_delay.*= (?P<delay>\S+)\s\n'), 0.9 * read_period)
    print("\nNOR delay = {:.2f}p".format(max_nor / 1e-12))
    total_nor = max(max_precharge, max_decoder_delay) + max_nor
    print("Total NOR delay = {:.2f}p".format(total_nor / 1e-12))

print("----------------Energy Analysis---------------")

# Write energy

operations = ["Write", "Read", "AND", "NOR"]
duty_cycles = [write_duty, read_duty, read_duty, read_duty]
periods = [write_period, read_period, read_period, read_period]
patterns = [
    re.compile("STATE_DELAY.* FALL=1 TD=([0-9\.]+)n TARG"),
    re.compile("READ_DELAY.* FALL=1 TD=([0-9\.]+)n TARG"),
    re.compile("AND_DELAY.* FALL=1 TD=([0-9\.]+)n TARG"),
    re.compile("NOR_DELAY.* FALL=1 TD=([0-9\.]+)n TARG")
]
max_read = max(max_tri_state, max_and, max_nor)
output_delays = [max_q_delay, max_read, max_read, max_read]
op2_names = ["State transition", "Tri state transition", "AND Transition", "NOR Transition"]

total_read_decode = max(max_decoder_delay, max_precharge)
decode_times = [max_decoder_delay, total_read_decode, total_read_decode, total_read_decode]

if baseline:
    ops = 2
else:
    ops = 4

for i in range(ops):
    print("\n-----Energy for {} Operation----------\n".format(operations[i]))

    mid_time = float(search_file(stim_file, patterns[i])) * 1e-9
    operation_start_time = mid_time - duty_cycles[i]*periods[i] - setup_time

    op_decode_time = operation_start_time + max_decoder_delay
    op_end_time = mid_time + output_delays[i]

    op1_energy = measure_energy([operation_start_time, op_decode_time])
    print('Decode energy: ', op1_energy, '\n')

    op2_energy = measure_energy([mid_time, op_end_time])
    print('{} energy: '.format(op2_names[i]), op2_energy, '\n')

    print("\n---Total energy = {}----".format(op1_energy + op2_energy))
