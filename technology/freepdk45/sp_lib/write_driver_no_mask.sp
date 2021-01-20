************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram
* Top Cell Name: write_driver_no_mask
* View Name:     schematic
* Netlisted on:  Jan 16 04:44:40 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram
* Cell Name:    write_driver_no_mask
* View Name:    schematic
************************************************************************

.SUBCKT write_driver_no_mask bl br data data_bar en en_bar gnd vdd
MM13 net67 en gnd gnd NMOS_VTG W=500n L=50n m=1
MM6 br data_bar net67 gnd NMOS_VTG W=500n L=50n m=1
MM3 net66 en gnd gnd NMOS_VTG W=500n L=50n m=1
MM0 bl data net66 gnd NMOS_VTG W=500n L=50n m=1
MM10 net62 en_bar vdd vdd PMOS_VTG W=300n L=50n m=1
MM9 br data_bar net62 vdd PMOS_VTG W=300n L=50n m=1
MM2 net64 en_bar vdd vdd PMOS_VTG W=300n L=50n m=1
MM1 bl data net64 vdd PMOS_VTG W=300n L=50n m=1
.ENDS

