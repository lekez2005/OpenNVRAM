#!/bin/env python
import re
import os, sys

# Helper Function
def getArg(arg_n, val, prev = None):

    ret = prev
    arg = '--{}='.format(arg_n)

    if val.startswith(arg):
        ret = val[len(arg):]

    return ret

# Starts
design = ''
uop    = ''
brief  = False
debug  = False

for arg in sys.argv:

    design = getArg('design', arg, design)
    uop    = getArg('uop'   , arg, uop   )
    brief  = True if arg == '--brief' else brief
    debug  = True if arg == '--debug' else debug
    debug  = True if arg == '-d'      else debug

if   design == 'bp-vram': design = 'compute'
elif design == 'bs-vram': design = 'serial'
else                    : exit(1)

design_dir = '{}_256_128'.format(design)
base_dir   = 'openram/bl_sram' # sim dir

directory  = '{}/{}/{}'.format(base_dir, design_dir, uop)

if debug:
    print(directory)

os.environ["temp_folder"] = directory

try:
    from analyze_simulation import *
except ImportError:
    from .analyze_simulation import *


num_trials = 10

#print(sim_data.get_bus_binary("v({})".format("Xsram.Xbank0.Xbitcell_array.Xbit_r0_c{}.Q"), 32, 0e-9))

total_energy = measure_energy([0, sim_data.time[-1]])

if brief:
    print('{:.3g}'.format(total_energy/num_trials*1e12))
else:
    print("Energy per operation = {:.3g} pJ".format(total_energy/num_trials*1e12))
