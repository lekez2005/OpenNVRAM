************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram
* Top Cell Name: cell_6t_4_fingers
* View Name:     schematic
* Netlisted on:  Jan 13 19:53:37 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram
* Cell Name:    cell_6t_4_fingers
* View Name:    schematic
************************************************************************

.SUBCKT cell_6t_4_fingers BL BR WL vdd gnd
M3 Q QBAR gnd gnd NMOS_VTG W=205.00n L=50n m=1
M2 QBAR Q gnd gnd NMOS_VTG W=205.00n L=50n m=1
M1 BR WL QBAR gnd NMOS_VTG W=135.00n L=50n m=1
M0 Q WL BL gnd NMOS_VTG W=135.00n L=50n m=1
M5 Q QBAR vdd vdd PMOS_VTG W=90n L=50n m=1
M4 QBAR Q vdd vdd PMOS_VTG W=90n L=50n m=1
.ENDS

