************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram
* Top Cell Name: ml_sense_amp
* View Name:     schematic
* Netlisted on:  Jul 18 21:36:34 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram
* Cell Name:    ml_sense_amp
* View Name:    schematic
************************************************************************

.SUBCKT ml_sense_amp dout en gnd vcomp vdd vin
MM12 dout dout_bar gnd gnd NMOS_VTG W=250.0n L=50n m=1
MM10 net34 vcomp net33 gnd NMOS_VTG W=200n L=50n m=1
MM8 dout_bar vin net33 gnd NMOS_VTG W=200n L=50n m=1
MM9 net33 en gnd gnd NMOS_VTG W=150.0n L=50n m=2
MM7 net34 net34 vdd vdd PMOS_VTG W=300n L=50n m=1
MM6 dout_bar net34 vdd vdd PMOS_VTG W=300n L=50n m=1
MM11 dout dout_bar vdd vdd PMOS_VTG W=370.0n L=50n m=1
.ENDS

