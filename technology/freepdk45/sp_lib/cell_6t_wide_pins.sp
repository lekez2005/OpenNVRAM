************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram
* Top Cell Name: cell_6t_wide_pins
* View Name:     schematic
* Netlisted on:  Jan 12 20:28:16 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram
* Cell Name:    cell_6t_wide_pins
* View Name:    schematic
************************************************************************
.SUBCKT cell_6t_wide_pins BL BR WL vdd gnd
MM3 Q QBAR gnd gnd NMOS_VTG W=205.00n L=50n m=1
MM2 QBAR Q gnd gnd NMOS_VTG W=205.00n L=50n m=1
MM1 BR WL QBAR gnd NMOS_VTG W=135.00n L=50n m=1
MM0 Q WL BL gnd NMOS_VTG W=135.00n L=50n m=1
MM5 Q QBAR vdd vdd PMOS_VTG W=90n L=50n m=1
MM4 QBAR Q vdd vdd PMOS_VTG W=90n L=50n m=1
.ENDS

