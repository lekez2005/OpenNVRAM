#!/bin/env python
import re
import os, sys

sys.path.append("../..")
sys.path.append("..")

# os.environ["temp_folder"] =
from psf_reader import PsfReader

sim_dir = "/scratch/ota2/openram/bl_sram/baseline_32_32_fixed3/read"

stim_file = os.path.join(sim_dir, "stim.sp")
meas_file = os.path.join(sim_dir, "stim.measure")
sim_file = os.path.join(sim_dir, 'transient1.tran.tran')

sim_data = PsfReader(sim_file)

# try:
#     from analyze_simulation import *
# except ImportError:
#     from .analyze_simulation import *


print(sim_data.get_bus_binary("v({})".format("Xsram.Xbank0.Xbitcell_array.Xbit_r0_c{}.Q"), 32, 0e-9))
