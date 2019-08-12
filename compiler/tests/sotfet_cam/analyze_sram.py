#!/bin/env python

import re
import os
import sys
sys.path.append('..')
import numpy as np
from psf_reader import PsfReader

from matplotlib import pylab as plt

tech = 'cmos'
size = 64

period = 2e-9
duty_cycle = 0.4

search_duty = 0.4
setup_time = 0.015e-9

if tech == 'cmos':
    write_duty = 0.3
else:
    write_duty = 0.6

# sim_dir = '/scratch/ota2/openram/sotfet_cam'
sim_dir = os.path.join('/scratch/ota2/openram/openram_13_temp')

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

def measure_power(times):
    current = sim_data.get_signal('Vvdd:p', times[0], times[1])
    time = sim_data.slice_array(sim_data.time, times[0], times[1])
    return -np.trapz(current, time)*0.9

decoder_pattern = re.compile('decoder_a.*= (?P<delay>\S+)\s\n')
decoder_delays = [float(x) for x in decoder_pattern.findall(meas_str)]
valid_decoder_delays = list(filter(lambda x: x < 0.9*period, decoder_delays))
max_decoder_delay = max(valid_decoder_delays)
print('Decoder delay: ', max_decoder_delay)

# Write measurements

print('\n-----------------Write ops--------------------')


write_command_pattern = re.compile('(?P<label>state_delay_a.*_t(?P<time>[0-9_]+))\s+=\s+(?P<delay>.+)\n',
                                   re.IGNORECASE)
all_writes = list(write_command_pattern.finditer(meas_str))

write_delays = [float(x['delay']) for x in all_writes]
valid_write_delays = list(filter(lambda x: x < 0.9*period, write_delays))
max_write_time = max(valid_write_delays)

print('State transition time: ', max_write_time)
print('Total write time: ', max_write_time + max_decoder_delay, '\n')

unique_writes = set([x['time'] for x in all_writes])

for time_str in unique_writes:
    actual_time = next(get_command(x['label'])['start_time'] for x in all_writes if x['time'] == time_str)
    time = float(actual_time)*1e-9 - duty_cycle*period

    decode_time = [time - setup_time, time + max_decoder_delay]
    write_time = [time + duty_cycle * period, time + duty_cycle*period + max_write_time]
    print('Time = {:3g}n'.format(time * 1e9))
    print('Decoding energy: ', measure_power(decode_time))
    print('Write energy: ', measure_power(write_time))
    print('Total Write energy: ', measure_power(decode_time) + measure_power(write_time), '\n')


# Read measurements
print('\n-----------------Read ops--------------------')


read_command_pattern = re.compile('(?P<label>read_delay_.*_t(?P<time>[0-9_]+))\s+=\s+(?P<delay>.+)\n',
                                   re.IGNORECASE)
all_reads = list(read_command_pattern.finditer(meas_str))

read_delays = [float(x['delay']) for x in all_reads]
valid_read_delays = list(filter(lambda x: x < 0.9*period, read_delays))
max_read_time = max(valid_read_delays)

print('State transition time: ', max_read_time)
print('Total read time: ', max_read_time + max_decoder_delay, '\n')

unique_reads = set([x['time'] for x in all_reads])

for time_str in unique_reads:
    actual_time = next(get_command(x['label'])['start_time'] for x in all_reads if x['time'] == time_str)
    time = float(actual_time)*1e-9 - duty_cycle*period

    decode_time = [time - setup_time, time + max_decoder_delay]
    read_time = [time + duty_cycle * period, time + duty_cycle*period + max_read_time]
    print('Time = {:3g}n'.format(time * 1e9))
    print('Decoding energy: ', measure_power(decode_time))
    print('Read energy: ', measure_power(read_time))
    print('Total Read energy: ', measure_power(decode_time) + measure_power(read_time), '\n')
