************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram_sot
* Top Cell Name: sotfet_discharge_sense_amp
* View Name:     schematic
* Netlisted on:  Apr 25 02:52:09 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram_sot
* Cell Name:    sotfet_discharge_sense_amp
* View Name:    schematic
************************************************************************

.SUBCKT sotfet_discharge_sense_amp bl br dout dout_bar en gnd sampleb vdd vref
MM7 net020 net020 vdd vdd PMOS_VTG W=200n L=50n m=1
MM6 dout net020 vdd vdd PMOS_VTG W=200n L=50n m=1
MM4 dout_bar dout vdd vdd PMOS_VTG W=375.00n L=50n m=1
MM0 bl sampleb vdd vdd PMOS_VTG W=200n L=50n m=1
MM3 dout_bar dout gnd gnd NMOS_VTG W=250.0n L=50n m=1
MM10 net020 bl net019 gnd NMOS_VTG W=200n L=50n m=1
MM8 dout vref net019 gnd NMOS_VTG W=200n L=50n m=1
MM9 net019 en gnd gnd NMOS_VTG W=200n L=50n m=1
.ENDS

