************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram_sot
* Top Cell Name: sotfet_ml_latched_sense_amp
* View Name:     schematic
* Netlisted on:  Sep 13 20:48:24 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram_sot
* Cell Name:    sotfet_ml_latched_sense_amp
* View Name:    schematic
************************************************************************

.SUBCKT sotfet_ml_latched_sense_amp dout en gnd vcomp vdd vin
MM12 dout dout_bar gnd gnd NMOS_VTG W=250.0n L=50n m=1
MM10 net34 vcomp_int net33 gnd NMOS_VTG W=200n L=50n m=1
MM8 dout_bar vin_int net33 gnd NMOS_VTG W=200n L=50n m=1
MM9 net33 en gnd gnd NMOS_VTG W=300n L=50n m=1
MM3 vin en vin_int vdd PMOS_VTG W=200n L=50n m=1
MM2 vcomp_int en vcomp vdd PMOS_VTG W=200n L=50n m=1
MM7 net34 net34 vdd vdd PMOS_VTG W=300n L=50n m=1
MM6 dout_bar net34 vdd vdd PMOS_VTG W=300n L=50n m=1
MM11 dout dout_bar vdd vdd PMOS_VTG W=370.0n L=50n m=1
.ENDS

