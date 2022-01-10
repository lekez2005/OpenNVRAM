************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram
* Top Cell Name: tgate_column_mux
* View Name:     schematic
* Netlisted on:  Mar  7 04:14:13 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram
* Cell Name:    tgate_column_mux
* View Name:    schematic
************************************************************************

.SUBCKT tgate_column_mux bl br bl_out br_out sel vdd gnd
MM5 br_out sel_buf br gnd NMOS_VTG W=720.0n L=50n m=1
MM2 bl_out sel_buf bl gnd NMOS_VTG W=720.0n L=50n m=1
MM0 sel_buf sel_bar gnd gnd NMOS_VTG W=180.0n L=50n m=1
MM12 sel_bar sel gnd gnd NMOS_VTG W=180.0n L=50n m=1
MM4 br_out sel_bar br vdd PMOS_VTG W=720.0n L=50n m=1
MM3 bl_out sel_bar bl vdd PMOS_VTG W=720.0n L=50n m=1
MM1 sel_buf sel_bar vdd vdd PMOS_VTG W=280.0n L=50n m=1
MM11 sel_bar sel vdd vdd PMOS_VTG W=280.0n L=50n m=1
.ENDS

