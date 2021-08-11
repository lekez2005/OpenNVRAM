************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram
* Top Cell Name: cam_cell_6t
* View Name:     schematic
* Netlisted on:  Jul 17 11:48:36 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram
* Cell Name:    cam_cell_6t
* View Name:    schematic
************************************************************************

.SUBCKT cam_cell_6t BL BR WL ML vdd gnd
MM9 net55 BR gnd gnd NMOS_VTG W=180.0n L=50n m=1
MM8 ML Q net55 gnd NMOS_VTG W=180.0n L=50n m=1
MM7 net57 BL gnd gnd NMOS_VTG W=180.0n L=50n m=1
MM6 ML QBAR net57 gnd NMOS_VTG W=180.0n L=50n m=1
MM1 BR WL QBAR gnd NMOS_VTG W=135.00n L=50n m=1
MM2 QBAR Q gnd gnd NMOS_VTG W=205.00n L=50n m=1
MM3 Q QBAR gnd gnd NMOS_VTG W=205.00n L=50n m=1
MM0 Q WL BL gnd NMOS_VTG W=135.00n L=50n m=1
MM4 QBAR Q vdd vdd PMOS_VTG W=90n L=50n m=1
MM5 Q QBAR vdd vdd PMOS_VTG W=90n L=50n m=1
.ENDS

