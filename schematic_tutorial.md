# Schematic simulation tutorial

# Import From cadence

## Create schematic in cadence, note the library and cell_view

## Import to openram using to_spice.py


set library and scratch in to_spice.py

output is and_gate.sp

.SUBCKT and_gate A B  out vdd gnd
MM5 out custom_name gnd gnd nch_mac l=30n w=100n m=1 nf=1
MM1 net14 A gnd gnd nch_mac l=30n w=100n m=1 nf=1
MM0 custom_name B net14 gnd nch_mac l=30n w=100n m=1 nf=1
MM4 out custom_name vdd vdd pch_mac l=30n w=200n m=1 nf=1
MM3 custom_name B vdd vdd pch_mac l=30n w=200n m=1 nf=1
MM2 custom_name A vdd vdd pch_mac l=30n w=200n m=1 nf=1
.ENDS

port order is random, change to desired

# Create bogus layout including all pins
# Import using to_gds.py
# output will be a gds with name.gds



# All schematics/layouts inherit from design class
# designs imported from spice should use library_import annotation

Create python file using library_import annotation

pin_names should match port order
pin_names = "A B  out vdd gnd".split()

lib_name should match subckt name

---------------------------------------------
# Create schematic in openram






For analysis, libpsf for reading Cadence psf format i.e. the simulation data
format

# libpsf has bugs, install from https://github.com/lekez2005/libpsf

pip install bindings/python/dist/https://github.com/lekez2005/libpsf/blob/master/bindings/python/dist/libpsf-0.0.1-cp37-cp37m-linux_x86_64.whl