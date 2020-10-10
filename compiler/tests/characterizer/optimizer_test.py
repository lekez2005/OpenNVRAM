#!/usr/bin/env python3

import numpy as np
import sympy as sp
from char_test_base import CharTestBase





t = CharTestBase()
t.initialize_tests(t.config_template)

from characterizer.delay_optimizer import LoadOptimizer
from characterizer.delay_loads import DistributedLoad, WireLoad, ParasiticLoad


def test():

    import matplotlib
    matplotlib.use("Qt5Agg")
    import numpy as np
    import matplotlib.pyplot as plt
    sizes = [1, 4, 16]
    lengths = np.linspace(0, 400, 50)
    for i in range(len(sizes)):

        inv = ParasiticLoad(size=sizes[i])
        delays = [inv.delay() + WireLoad(inv, length).delay() for length in lengths]
        plt.plot(lengths, delays)

    plt.legend(sizes)
    plt.show()


num_stages = 3


wire_driver = WireLoad(None, 20)
load = DistributedLoad(wire_driver, cap_per_stage=0.3e-15, stage_width=1.3, num_stages=64)
load2 = DistributedLoad(wire_driver, cap_per_stage=0.6e-15, stage_width=1, num_stages=64)

initial_guess, opt_func, total_delay, stage_delays = LoadOptimizer.\
    generate_en_en_bar_delay(num_stages, [load], [load2], 1)

# initial_guess, opt_func, total_delay, stage_delays = LoadOptimizer.\
#     generate_precharge_delay(num_stages, 64, wire_driver, load, 1)

# sympy
sym_vars = sp.var(', '.join(reversed([chr(ord('z') - x) for x in range(num_stages)])))
func = opt_func(sym_vars)
print(func)

def print_list(l):
    print('[', ', '.join(["{:2g}".format(x) for x in l]), ']')

#initial_guess = np.asarray([1, 1, 1])
#constraint = LinearConstraint(np.eye(num_stages), np.ones(num_stages), 50*np.ones(num_stages), keep_feasible=True)
# print(initial_guess)

result = LoadOptimizer.minimize_sizes(opt_func, initial_guess, max_delay=120, all_stage_delays=stage_delays,
                                      final_stage=False, equalize_final_stages=False)
# result = LoadOptimizer.minimize_delays(opt_func, initial_guess, max_size=25)


print_list(result.x)
print_list(stage_delays(result.x))
print(total_delay(result.x))

