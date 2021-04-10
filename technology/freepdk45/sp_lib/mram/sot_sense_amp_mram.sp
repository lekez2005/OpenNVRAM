************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram_sot
* Top Cell Name: sot_sense_amp_mram
* View Name:     schematic
* Netlisted on:  Apr  6 03:05:37 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram_sot
* Cell Name:    sot_sense_amp_mram
* View Name:    schematic
************************************************************************

.SUBCKT sot_sense_amp_mram bl br dout_bar en en_bar gnd vclamp vdd vref
MM5 vdata vclamp bl gnd NMOS_VTG W=200n L=50n m=1
MM9 net10 en gnd gnd NMOS_VTG W=200n L=50n m=1
MM10 net11 vdata net10 gnd NMOS_VTG W=200n L=50n m=1
MM8 dout vref net10 gnd NMOS_VTG W=200n L=50n m=1
MM12 dout_bar dout gnd gnd NMOS_VTG W=250.0n L=50n m=1
MM4 vdata vref net18 vdd PMOS_VTG W=200n L=50n m=1
MM1 net18 en_bar vdd vdd PMOS_VTG W=200n L=50n m=1
MM11 dout_bar dout vdd vdd PMOS_VTG W=375.00n L=50n m=1
MM7 net11 net11 vdd vdd PMOS_VTG W=200n L=50n m=1
MM6 dout net11 vdd vdd PMOS_VTG W=200n L=50n m=1
.ENDS

