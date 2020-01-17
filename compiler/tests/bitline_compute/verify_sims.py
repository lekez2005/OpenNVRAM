#!/bin/env python
import re
import os, sys

os.environ["temp_folder"] = "/work/global/ka429/vlsi/cadence/gen_tmp/openram/bl_sram/serial_32_32"

#try:
from analyze_simulation import *
#except ImportError:
#    from .analyze_simulation import *

array = open('verify.data', 'r')
with open('verify.data', 'r') as _file:
    array = _file.read()

num_trials = 10

verify_entries = eval('[{}]'.format(array))

for entry in verify_entries:
    _measured = sim_data.get_bus_binary("v({})".format('Xsram.Xbank0.DATA[{}]'), 32, (entry[0] - 1.5) * 1e-9)

    measured = [e for e in _measured]

    expected = entry[1]

    print('At time = {} ns'.format(entry[0]))
    print('    Expected = {}'.format(expected))
    print('    Measured = {}'.format(measured))

    equal = measured == expected

    if not equal:
        print('    NOT EQUAL')

#total_energy = measure_energy([0, sim_data.time[-1]])

#print("Energy per operation = {:.3g} pJ".format(total_energy/num_trials*1e12))
