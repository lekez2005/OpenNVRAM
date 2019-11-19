#!/bin/env python

import os
import re
import sys

import numpy as np

sys.path.append("..")
from sim_analyzer import setup


usim = False
sotfet = True
tech = "sotfet" if sotfet else 'cmos'
num_rows = 64
num_cols = 64
separate_vdd = False
address_width = int(np.log2(num_rows))

suffix = "_usim"*usim

# sim_dir = '/scratch/ota2/openram/sotfet_cam'
sim_dir = os.path.join('/scratch/ota2/openram/sotfet_cam', '{0}_{1}_{2}{3}'.format(tech, num_cols, num_rows, suffix))

setup(num_cols_=num_cols, num_rows_=num_rows, sim_dir_=sim_dir)

from sim_analyzer import sim_data, digit_regex, standardize_pattern, extract_probe_pattern,\
    measure_delay_from_meas, get_address_data
import sim_analyzer


def search_stim(pattern):
    return sim_analyzer.search_file(sim_analyzer.stim_file, pattern)


def measure_energy(times, verbose=False):
    if separate_vdd:
        vdd_names = ["vdd_wordline", "vdd_decoder", "vdd_logic_buffers", "vdd_data_flops", "vdd_bitline_buffer",
                     "vdd_bitline_logic", "vdd_sense_amp", "vdd"]
    else:
        vdd_names = ["vdd"]
    total_power = 0
    for net in vdd_names:
        current = sim_data.get_signal('V{}:p'.format(net), times[0], times[1])
        time = sim_data.slice_array(sim_data.time, times[0], times[1])
        power = -np.trapz(current, time) * 0.9
        total_power += power
        if net == 'vdd':
            net = 'vdd_precharge'
        if verbose:
            print("{} energy = {}".format(net, power))
    if verbose:
        print()
    return total_power


def get_address(time_):
    return sim_analyzer.vector_to_int(sim_data.get_bus_binary(address_pattern, address_width, time_))


delay_regex = "(?P<delay>\S+)\s\n"

saved_addresses = list(map(int, search_stim("saved addresses = (.*)").split(",")))

search_period = float(search_stim("search period = {}n".format(digit_regex)))*1e-9
write_period = float(search_stim("write period = {}n".format(digit_regex)))*1e-9
search_duty = float(search_stim("search_duty = {}".format(digit_regex)))
write_duty = float(search_stim("write_duty = {}".format(digit_regex)))

address_pattern = "A[{}]"
clk_reference = "v(" + re.search(".meas tran {}.* TRIG v\((\S+)\) VAL".format("STATE_DELAY"),
                                 sim_analyzer.stim_str).group(1) + ")"

sim_analyzer.clk_reference = clk_reference

ml_pattern = standardize_pattern(extract_probe_pattern("ML_rise"))
dout_pattern = standardize_pattern(extract_probe_pattern("dout_fall"))

# Precharge delay
max_precharge, _ = measure_delay_from_meas(re.compile('ml_rise_a.*= {}'.format(delay_regex)),
                                           write_duty * write_period)

max_dout, _ = measure_delay_from_meas(re.compile('dout_fall_a.*= {}'.format(delay_regex)),
                                      write_duty * write_period)

print('\n-----------------Search ops--------------------')

print('Precharge:\t\t {:.4g} ps'.format(max_precharge*1e12))
print('Search match:\t {:.4g} ps'.format(max_dout*1e12))
print('Total Search:\t {:.4g} ps \n'.format((max_precharge + max_dout)*1e12))

search_times = [1e-9*float(x) for x in search_stim("t = ([0-9\.]+) Search .*")]

all_precharges = []
for search_time in search_times:
    mid_cycle = search_time + search_duty*search_period
    cycle_end = search_time + search_period
    precharge_energy = measure_energy((search_time, mid_cycle))
    search_energy = measure_energy((mid_cycle, cycle_end))
    print("t = {:2g} ns \t Precharge energy = {:.3g} pJ \t Search energy = {:.3g} pJ".format(search_time*1e9,
          precharge_energy*1e12, search_energy*1e12))

    # verify search
    search_data = sim_data.get_bus_binary(sim_analyzer.data_pattern, num_cols, mid_cycle)
    search_mask = sim_data.get_bus_binary(sim_analyzer.mask_pattern, num_cols, mid_cycle)
    for address in saved_addresses:
        current_data = get_address_data(address, search_time)
        matches = [(not z) or x == y for x, y, z in zip(current_data, search_data, search_mask)]
        expected_match = all(matches)
        actual_match = bool(sim_data.get_binary(dout_pattern.format(address), cycle_end)[0])
        if not expected_match == actual_match:
            print("Search failure at time {:.3g} ns address {}".format(search_time*1e9, address))

# Write measurements
print('\n-----------------Write ops--------------------')

# Decoder delay
max_decoder_delay, _ = measure_delay_from_meas(re.compile('decoder_a.*= {}'.format(delay_regex)), 0.9 * write_period)

print('Decoder delay: \t{:.4g} ps'.format(max_decoder_delay*1e12))

if not sotfet:
    max_write_delay, _ = measure_delay_from_meas(re.compile('state_delay_a.*= {}'.format(delay_regex)),
                                                 0.9 * write_period)

    print('State delay: \t{:.4g} ps'.format(max_write_delay * 1e12))
    print('Total write : \t{:.4g} ps\n'.format((max_decoder_delay + max_write_delay) * 1e12))


write_times = [1e-9*float(x) for x in search_stim("t = ([0-9\.]+) Write .*")]

sim_analyzer.period = write_period
sim_analyzer.duty_cycle = write_duty

for write_time in write_times:
    mid_cycle = write_time + write_duty*write_period
    cycle_end = write_time + write_period
    first_half_energy = measure_energy((write_time, mid_cycle))
    second_half_energy = measure_energy((mid_cycle, cycle_end))
    print("t = {:.4g} ns \t First energy = {:.3g} pJ   \t Second energy = {:.3g} pJ"
          .format(write_time * 1e9, first_half_energy * 1e12, second_half_energy * 1e12))

    # verify write
    write_address = get_address(mid_cycle)
    sim_analyzer.verify_write_event(write_time*1e9, write_address, sotfet)
