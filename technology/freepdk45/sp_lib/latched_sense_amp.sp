************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram
* Top Cell Name: latched_sense_amp
* View Name:     schematic
* Netlisted on:  Jan 15 05:57:10 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram
* Cell Name:    latched_sense_amp
* View Name:    schematic
************************************************************************

.SUBCKT latched_sense_amp bl br dout dout_bar en preb sampleb vdd gnd
MM13 dout outb_int vdd vdd PMOS_VTG W=225.00n L=50n m=2
MM11 dout_bar out_int vdd vdd PMOS_VTG W=225.00n L=50n m=2
MM8 outb_int out_int vdd vdd PMOS_VTG W=200n L=50n m=1
MM5 outb_int preb vdd vdd PMOS_VTG W=120.0n L=50n m=1
MM4 outb_int preb out_int vdd PMOS_VTG W=120.0n L=50n m=1
MM3 out_int preb vdd vdd PMOS_VTG W=120.0n L=50n m=1
MM2 out_int sampleb bl vdd PMOS_VTG W=200n L=50n m=1
MM1 out_int outb_int vdd vdd PMOS_VTG W=200n L=50n m=1
MM0 outb_int sampleb br vdd PMOS_VTG W=200n L=50n m=1
MM14 dout outb_int gnd gnd NMOS_VTG W=150.0n L=50n m=2
MM12 dout_bar out_int gnd gnd NMOS_VTG W=150.0n L=50n m=2
MM10 net24 en gnd gnd NMOS_VTG W=200n L=50n m=1
MM9 outb_int out_int net24 gnd NMOS_VTG W=200n L=50n m=1
MM7 net25 en gnd gnd NMOS_VTG W=200n L=50n m=1
MM6 out_int outb_int net25 gnd NMOS_VTG W=200n L=50n m=1
.ENDS

