#!/bin/env python
import json
import os
import re

import numpy as np

from cam_simulator import create_arg_parser, parse_options, get_sim_directory, CMOS_MODE

from sim_analyzer import digit_regex, standardize_pattern, extract_probe_pattern, \
    measure_delay_from_stim_measure
import sim_analyzer

arg_parser = create_arg_parser()
mode, options = parse_options(arg_parser)

openram_temp = get_sim_directory(options, mode)
cmos = mode == CMOS_MODE
sotfet = not cmos
slow_ramp = options.slow_ramp

verbose_save = options.verbose_save
series = options.series
sim_analyzer.word_size = options.num_cols

search_settling_time = 50e-12
write_settling_time = 200e-12

print("Simulation Dir = {}".format(openram_temp))
sim_analyzer.setup(num_cols_=options.num_cols, num_rows_=options.num_rows,
                   sim_dir_=openram_temp)

states_file = os.path.join(openram_temp, "state_probes.json")

sim_data = sim_analyzer.sim_data
sim_data.thresh = 0.45
data_thresh = sim_data.thresh if cmos else 0

with open(states_file, "r") as states_file_:
    state_probes = json.load(states_file_)

num_cols = options.num_cols
address_width = int(np.log2(options.num_rows))


def search_stim(pattern):
    return sim_analyzer.search_file(sim_analyzer.stim_file, pattern)


def get_address(time_):
    return sim_analyzer.vector_to_int(sim_data.get_bus_binary(
        address_pattern, address_width, time_))


def get_address_data(address, time):
    return original_get_address(address, time, state_probes, data_thresh)


original_get_address = sim_analyzer.get_address_data
sim_analyzer.get_address_data = get_address_data


delay_regex = "(?P<delay>\S+)\s\n"

saved_addresses = list(map(int, search_stim("saved addresses = (.*)").split(",")))

search_period = float(search_stim("search period = {}n".format(digit_regex))) * 1e-9
write_period = float(search_stim("write period = {}n".format(digit_regex))) * 1e-9
search_duty = float(search_stim("search_duty = {}".format(digit_regex)))
write_duty = float(search_stim("write_duty = {}".format(digit_regex)))

address_pattern = "A[{}]"
clk_reference = "v(" + re.search(".meas tran {}.* TRIG v\((\S+)\) VAL".format("STATE_DELAY"),
                                 sim_analyzer.stim_str).group(1) + ")"

sim_analyzer.clk_reference = clk_reference

ml_pattern = standardize_pattern(extract_probe_pattern("ML_rise"))
dout_pattern = "v(search_out[{}])"

# Precharge delay
max_precharge, _ = measure_delay_from_stim_measure("ml_rise",
                                                   max_delay=search_duty * search_period)

max_dout, dout_delays = measure_delay_from_stim_measure("dout_fall",
                                                        max_delay=(search_duty * search_period +
                                                                   search_settling_time))

print("Search period = {:.3g}, first  = {:.3g}".format(search_period*1e9, search_duty*search_period*1e9))
print("Write period = {:.3g}, first = {:.3g}".format(write_period*1e9, write_duty*write_period*1e9))

print('\n-----------------Search ops--------------------')

print('Precharge:\t\t {:.4g} ps'.format(max_precharge * 1e12))
print('Search match:\t {:.4g} ps'.format(max_dout * 1e12))
print('Total Search:\t {:.4g} ps \n'.format((max_precharge + max_dout) * 1e12))


search_times = list(sorted([1e-9 * float(x) for x in search_stim("t = ([0-9\.]+) Search .*")]))

all_precharges = []
for search_time in search_times:
    mid_cycle = search_time + search_duty * search_period
    cycle_end = search_time + search_period + search_settling_time
    precharge_energy = sim_analyzer.measure_energy((search_time, mid_cycle))
    search_energy = sim_analyzer.measure_energy((mid_cycle, cycle_end))
    print("t = {:2g} ns \t Precharge energy = {:.3g} pJ \t Search energy = {:.3g} pJ \t Total = {:.3g} pJ".
          format(search_time * 1e9,
                 precharge_energy * 1e12, search_energy * 1e12, (precharge_energy + search_energy) * 1e12))

    # verify search
    search_data = sim_data.get_bus_binary(sim_analyzer.data_pattern, num_cols, mid_cycle)
    if not cmos and not series:
        search_data = [int(not x) for x in search_data]
    search_mask = sim_data.get_bus_binary(sim_analyzer.mask_pattern, num_cols, mid_cycle)
    for address in saved_addresses:
        current_data = get_address_data(address, search_time)
        matches = [(not z) or x == y for x, y, z in zip(current_data, search_data, search_mask)]
        expected_match = all(matches)
        actual_match = bool(sim_data.get_binary(dout_pattern.format(address), cycle_end)[0])
        if not expected_match == actual_match:
            sim_analyzer.debug_error("Search error", search_data, current_data)
            # breakpoint()
            print("Search failure at time {:.3g} ns address {}".format(search_time * 1e9, address))

# Write measurements
print('\n-----------------Write ops--------------------')

# Decoder delay
max_decoder_delay, _ = measure_delay_from_stim_measure("decoder", max_delay=0.9 * write_period)

print('Decoder delay: \t{:.4g} ps'.format(max_decoder_delay * 1e12))

if not sotfet:
    max_write_delay, _ = measure_delay_from_stim_measure("state_delay",
                                                         max_delay=0.9 * write_period)

    print('State delay: \t{:.4g} ps'.format(max_write_delay * 1e12))
    print('Total write : \t{:.4g} ps\n'.format((max_decoder_delay + max_write_delay) * 1e12))

write_times = list(sorted([1e-9 * float(x) for x in search_stim("t = ([0-9\.]+) Write .*")]))

sim_analyzer.period = write_period
sim_analyzer.duty_cycle = write_duty

for write_time in write_times:
    mid_cycle = write_time + write_duty * write_period
    cycle_end = write_time + write_period
    first_half_energy = sim_analyzer.measure_energy((write_time, mid_cycle))
    second_half_energy = sim_analyzer.measure_energy((mid_cycle, cycle_end))
    print("t = {:.4g} ns \t First energy = {:.3g} pJ   \t Second energy = {:.3g} pJ \t Total = {:.3g} pJ"
          .format(write_time * 1e9, first_half_energy * 1e12, second_half_energy * 1e12,
                  (first_half_energy + second_half_energy) * 1e12))

    # verify write
    write_address = get_address(mid_cycle)
    sim_analyzer.verify_write_event(write_time, write_address,
                                    write_period + write_settling_time,
                                    write_duty,
                                    negate=series)
