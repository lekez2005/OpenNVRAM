#!/bin/env python
import os
import re

import numpy as np

from shared_simulator import create_arg_parser, parse_options, get_sim_directory, CMOS_MODE
from psf_reader import PsfReader

arg_parser = create_arg_parser()
arg_parser.add_argument("-v", "--verbose", action="count", default=0)
mode, options = parse_options(arg_parser)
openram_temp = get_sim_directory(options, mode) + "_next"
cmos = mode == CMOS_MODE

stim_file = os.path.join(openram_temp, "stim.sp")
sim_file = os.path.join(openram_temp, "tran.tran.tran")
sim_data = PsfReader(sim_file, vdd_name=None)
sim_data.vdd = 0.9

print("Sim dir = {}".format(openram_temp))


def search_stim(pattern):
    with open(stim_file, 'r') as file:
        content = file.read()
        matches = re.findall(pattern, content)
    return matches


def measure_energy(start_time, end_time):
    current = sim_data.get_signal('Vvdd:p', start_time, end_time)
    time = sim_data.slice_array(sim_data.time, start_time, end_time)
    energy = -np.trapz(current, time) * sim_data.vdd
    return energy


op_pattern = r"-- {}.*t = ([0-9\.]+) period = ([0-9\.]+)"
read_ops = search_stim(op_pattern.format("READ"))
write_ops = search_stim(op_pattern.format("WRITE"))

clk_probe = "v(" + search_stim(r"--clk_buf_probe=(\S+)--")[0] + ")"

all_ops = [("read", read_ops), ("write", write_ops)]

read_period = write_period = 0

def energy_format(l):
    return ", ".join(["{:.3g}".format(x) for x in l])

for op_name, op_events in all_ops:
    op_energies = []
    for op_time, op_period in op_events[:10]:
        op_time = float(op_time) * 1e-9
        op_period = float(op_period) * 1e-9
        max_op_start = op_time + 0.5 * op_period
        clk_ref_time = sim_data.get_transition_time_thresh(clk_probe, op_time,
                                                           stop_time=max_op_start,
                                                           edgetype=sim_data.RISING_EDGE)
        op_energy = measure_energy(clk_ref_time, clk_ref_time + op_period)
        op_energies.append(op_energy)
        if op_name == "read":
            read_period = op_period
        else:
            write_period = op_period

    op_energies = [x*1e12 for x in op_energies]
    print("Initial energies", energy_format(op_energies))
    op_energies = op_energies[2:]
    print("Used energies: ", energy_format(op_energies))

    print("Mean {} energy = {:.3g} pJ".format(op_name.capitalize(),
                                              sum(op_energies) / len(op_energies)))

leakage_op = search_stim(r" -- LEAKAGE start = (\S+) end = (\S+)")[0]
leakage_start, leakage_end = [1e-9*float(x) + 9*read_period for x in leakage_op]
print(leakage_start, leakage_end)
total_leakage = measure_energy(leakage_start, leakage_end)

leakage_power = total_leakage / (leakage_end - leakage_start)
leakage_write = leakage_power * write_period
leakage_read = leakage_power * read_period

print("Leakage Power = {:.3g} mW".format(leakage_power*1e3))
print("Write leakage = {:.3g} pJ".format(leakage_write*1e12))
print("Read leakage = {:.3g} pJ".format(leakage_read*1e12))
