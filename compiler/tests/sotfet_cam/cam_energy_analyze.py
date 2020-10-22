#!/bin/env python
import numpy as np

from cam_simulator import create_arg_parser, parse_options, get_sim_directory, CMOS_MODE

from sim_analyzer import measure_energy
import sim_analyzer

arg_parser = create_arg_parser()
arg_parser.add_argument("-v", "--verbose", action="count", default=0)
mode, options = parse_options(arg_parser)
openram_temp = get_sim_directory(options, mode)

print("Simulation Dir = {}".format(openram_temp))
sim_analyzer.setup(num_cols_=options.num_cols, num_rows_=options.num_rows,
                   sim_dir_=openram_temp)

sim_data = sim_analyzer.sim_data
sim_data.vdd = 0.9

print("Sim dir = {}".format(openram_temp))


def search_stim(pattern):
    return sim_analyzer.search_file(sim_analyzer.stim_file, pattern)


op_pattern = r"-- {}.*t = ([0-9\.]+) period = ([0-9\.]+)"
search_ops = search_stim(op_pattern.format("SEARCH"))
write_ops = search_stim(op_pattern.format("WRITE"))


clk_probe = "v(" + search_stim(r"--clk_buf_probe=(\S+)--") + ")"

print(clk_probe)

all_ops = [("search", search_ops), ("write", write_ops)]

search_period = write_period = 0

for op_name, op_events in all_ops:
    op_energies = []
    for op_time, op_period in op_events:
        op_time = float(op_time) * 1e-9
        op_period = float(op_period) * 1e-9
        max_op_start = op_time + 0.5 * op_period
        clk_ref_time = sim_data.get_transition_time_thresh(clk_probe, op_time,
                                                           stop_time=max_op_start,
                                                           edgetype=sim_data.RISING_EDGE)
        op_energy = measure_energy((clk_ref_time, clk_ref_time + op_period))
        op_energies.append(op_energy)
        if op_name == "search":
            search_period = op_period
        else:
            write_period = op_period

    print("{} energies = [{}]".format(op_name.capitalize(),
                                      ", ".join(["{:.3g}".format(x * 1e12) for x in op_energies])))
    print("Mean {} energy = {:.3g} pJ".format(op_name.capitalize(),
                                              1e12 * sum(op_energies) / len(op_energies)))

leakage_op = search_stim(r" -- LEAKAGE start = (\S+) end = (\S+)")

leakage_start, leakage_end = [1e-9 * float(x) for x in leakage_op]
total_leakage = measure_energy((leakage_start, leakage_end))

leakage_power = total_leakage / (leakage_end - leakage_start)
leakage_write = leakage_power * write_period
leakage_search = leakage_power * search_period

print("Leakage Power = {:.3g} mW".format(leakage_power * 1e3))
print("Write leakage = {:.3g} pJ".format(leakage_write * 1e12))
print("Search leakage = {:.3g} pJ".format(leakage_search * 1e12))
