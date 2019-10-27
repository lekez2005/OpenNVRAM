#!/bin/env python
import re

try:
    from analyze_simulation import *
except ImportError:
    from .analyze_simulation import *


def find_saved_matches(pattern):
    pattern = "Xsram\.\S*{}\S*:d".format(pattern)
    return re.findall(pattern, all_saved_signals)


def sum_energy(signals, start_time, end_time):
    time = sim_data.slice_array(sim_data.time, start_time, end_time)
    total_energy = 0
    for sig in signals:
        current = sim_data.get_signal(sig, start_time, end_time)
        total_energy += -np.trapz(current, time) * 0.9

    return total_energy


leakage_time = 1e-9*float(re.search("\*\*\* t = ([0-9\.]+)", stim_str).group(1)) + 3*period
sim_length = sim_data.time[-1]
all_leakage = measure_energy([leakage_time, sim_length])
leakage_per_cycle = all_leakage/(sim_length - leakage_time)*period


event_times = [1e-9*float(x) for x in re.findall("^\* t = ([0-9\.]+)", stim_str, re.M)]
start_time = min(event_times)
end_time = max(event_times) + period

all_times = [(x, x+period) for x in event_times] + [(leakage_time, sim_length)]

# all_times = [(min(event_times), max(event_times) + period)]

count = 0
for start_time, end_time in all_times:

    total_energy = measure_energy([start_time, end_time])

    write_sigs = find_saved_matches("mXbank0_Xwrite_driver_array")
    write_driver_energy = sum_energy(write_sigs, start_time, end_time)

    sense_energy = sum_energy(find_saved_matches("mXbank0_Xsense_amp_array_Xsa"), start_time, end_time)
    precharge_energy = sum_energy(find_saved_matches("mXbank0_Xprecharge_array_Xpre_column"), start_time, end_time)

    buffers_energy = sum_energy(find_saved_matches("mXbank0_Xcontrol_buffers_X"), start_time, end_time)
    wordline_energy = sum_energy(find_saved_matches("mXbank0_Xwordline_driver_Xdriver"), start_time, end_time)
    bitcell_energy = sum_energy(find_saved_matches("mXbank0_Xbitcell_array_Xbit"), start_time, end_time)

    print("Read: " if count % 2 == 0 else "Write: ")

    print("Total energy \t\t = {:.2g}pJ".format(total_energy*1e12))
    print("Bitcell Leakage \t = {:.2g}pJ".format(leakage_per_cycle*1e12))
    print("Bitcell Array \t\t = {:.2g}pJ".format(bitcell_energy*1e12))
    print("Write Driver \t\t = {:.2g}pJ".format(write_driver_energy*1e12))
    print("Sense Amps \t\t\t = {:.2g}pJ".format(-sense_energy*1e12))
    print("Precharge \t\t\t = {:.2g}pJ".format(precharge_energy*1e12))
    print("Wordline Driver \t = {:.2g}pJ".format(wordline_energy*1e12))
    print("Control Buffers \t = {:.2g}pJ".format(buffers_energy*1e12))
    print("_"*60)

    count += 1
# print("Write en Buf \t\t = {:.2g}pJ".format(write_buf_energy*1e12))
