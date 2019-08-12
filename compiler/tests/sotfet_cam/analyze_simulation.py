#!/bin/env python

import os
import re
import sys

sys.path.append('..')
import numpy as np
from psf_reader import PsfReader

tech = 'sotfet'
size = 64

search_period = 2e-9
write_period = 3e-9
search_duty = 0.4
setup_time = 0.015e-9

if tech == 'cmos':
    write_duty = 0.3
else:
    write_duty = 0.6

# sim_dir = '/scratch/ota2/openram/sotfet_cam'
sim_dir = os.path.join('/scratch/ota2/openram/sotfet_cam', '{0}_{1}_{1}'.format(tech, size))

stim_file = os.path.join(sim_dir, "stim.sp")
meas_file = os.path.join(sim_dir, "stim.measure")

sim_file = os.path.join(sim_dir, 'transient1.tran.tran')
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
    for net in ["vdd_wordline", "vdd_decoder", "vdd_logic_buffers", "vdd_data_flops", "vdd_bitline_buffer",
                "vdd_bitline_logic", "vdd_sense_amp", "vdd"]:

        current = sim_data.get_signal('V{}:p'.format(net), times[0], times[1])
        time = sim_data.slice_array(sim_data.time, times[0], times[1])
        power = -np.trapz(current, time)*0.9
        total_power += power
        if net == 'vdd':
            net = 'vdd_precharge'
        if verbose:
            print("{} energy = {}".format(net, power))
    print()
    return total_power

# Search measurements

search_op_pattern = '(?P<label>{}(?P<address>[0-9]+)_(?P<time>[0-9_]+))\s+=\s+(?P<delay>.+)\n'

# get search times
ml_rise_pattern = re.compile(search_op_pattern.format('ml_rise_a'))
all_rise = list(ml_rise_pattern.finditer(meas_str))

ml_rise_pattern.search(meas_str)

unique_searches = set([x['time'] for x in all_rise])

rise_times = [float(x['delay']) for x in all_rise]
valid_rise_times = list(filter(lambda x: x < 0.9*search_period, rise_times))
max_rise_time = max(valid_rise_times)

fall_results = list(re.compile(search_op_pattern.format('dout_fall_a')).finditer(meas_str))
fall_times = [float(x['delay']) for x in fall_results]
valid_fall_times = list(filter(lambda x: x < 0.9*search_period, fall_times))
max_fall_time = max(valid_fall_times)

print('\n-----------------Search ops--------------------')
print('Search precharge time: ', max_rise_time)
print('Search match time: ', max_fall_time)
print('Search delay = ', max_rise_time + max_fall_time, '\n')

for time_str in unique_searches:
    actual_time = next(get_command(x['label'])['start_time'] for x in all_rise if x['time'] == time_str)
    time = float(actual_time)*1e-9
    precharge_time = [time-setup_time, time+max_rise_time]
    discharge_time = [time+search_duty*search_period, time+search_duty*search_period+max_fall_time]
    print('Time = {:3g}n'.format(time*1e9))
    print('Precharge Search energy: ', measure_energy(precharge_time), '\n')
    print('Match Search energy: ', measure_energy(discharge_time), '\n')
    print('Total search energy: ', measure_energy(precharge_time) + measure_energy(discharge_time), '\n')

# Write measurements
print('\n-----------------Write ops--------------------')

decoder_pattern = re.compile('decoder_a.*= (?P<delay>\S+)\s\n')
decoder_delays = [float(x) for x in decoder_pattern.findall(meas_str)]
max_decoder_delay = max(decoder_delays)

print('Decoder delay: ', max_decoder_delay)


write_command_pattern = re.compile('(?P<label>state_delay_a.*_t(?P<time>[0-9_]+))\s+=\s+(?P<delay>.+)\n',
                                   re.IGNORECASE)
all_writes = list(write_command_pattern.finditer(meas_str))

write_delays = [float(x['delay']) for x in all_writes]
valid_write_delays = list(filter(lambda x: x < (1-write_duty)*write_period, write_delays))

if tech == "sotfet": # get initial cross points
    cross_command_pattern = re.compile('(?P<label>state_cross_a.*_t(?P<time>[0-9_]+))\s+=\s+(?P<delay>.+)\n',
                                       re.IGNORECASE)
    all_cross = list(cross_command_pattern.finditer(meas_str))
    cross_delays = [float(x['delay']) for x in all_cross]
    valid_cross_delays = list(filter(lambda x: x < 0.9 * write_period, cross_delays))
    max_cross_delay = max(valid_cross_delays)
    print('State cross time: ', max_cross_delay)
else:
    max_cross_delay = 0


max_write_time = max(valid_write_delays) + max_cross_delay

print('State transition time: ', max_write_time)
print('Total write time: ', max_write_time + max_decoder_delay, '\n')

unique_writes = set([x['time'] for x in all_writes])

for time_str in unique_writes:
    actual_time = next(get_command(x['label'])['start_time'] for x in all_writes if x['time'] == time_str)
    time = float(actual_time)*1e-9 - write_duty*write_period

    decode_time = [time - setup_time, time + max_decoder_delay]
    discharge_time = [time + write_duty * write_period, time + write_duty*write_period + max_write_time]
    print('Time = {:3g}n'.format(time * 1e9))
    print('Decoding energy: ', measure_energy(decode_time), '\n')
    print('Write energy: ', measure_energy(discharge_time), '\n')
    print('Total Write energy: ', measure_energy(decode_time, verbose=False) +
          measure_energy(discharge_time, verbose=False), '\n')
