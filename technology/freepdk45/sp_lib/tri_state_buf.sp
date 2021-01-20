************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram
* Top Cell Name: tri_state_buf
* View Name:     schematic
* Netlisted on:  Jan 15 05:58:19 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram
* Cell Name:    tri_state_buf
* View Name:    schematic
************************************************************************

.SUBCKT tri_state_buf en en_bar gnd in_bar out vdd
MM8 net017 en gnd gnd NMOS_VTG W=150.0n L=50n m=1
MM3 net53 en gnd gnd NMOS_VTG W=150.0n L=50n m=1
MM0 out in_bar net53 gnd NMOS_VTG W=150.0n L=50n m=1
MM10 out in_bar net017 gnd NMOS_VTG W=150.0n L=50n m=1
MM9 out in_bar net018 vdd PMOS_VTG W=225.00n L=50n m=1
MM7 net018 en_bar vdd vdd PMOS_VTG W=225.00n L=50n m=1
MM2 net52 en_bar vdd vdd PMOS_VTG W=225.00n L=50n m=1
MM1 out in_bar net52 vdd PMOS_VTG W=225.00n L=50n m=1
.ENDS

