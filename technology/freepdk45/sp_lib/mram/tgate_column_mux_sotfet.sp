************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram_sot
* Top Cell Name: tgate_column_mux_sotfet
* View Name:     schematic
* Netlisted on:  Mar 27 04:17:46 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram_sot
* Cell Name:    tgate_column_mux_sotfet
* View Name:    schematic
************************************************************************

.SUBCKT tgate_column_mux_sotfet bl br bl_out br_out sel gnd vdd
MM5 br_out sel_buf br gnd NMOS_VTG W=800n L=50n m=1
MM2 bl_out sel_buf bl gnd NMOS_VTG W=800n L=50n m=1
MM0 sel_buf sel_bar gnd gnd NMOS_VTG W=180.0n L=50n m=1
MM12 sel_bar sel gnd gnd NMOS_VTG W=180.0n L=50n m=1
MM4 br_out sel_bar br vdd PMOS_VTG W=1.2u L=50n m=1
MM3 bl_out sel_bar bl vdd PMOS_VTG W=1.2u L=50n m=1
MM1 sel_buf sel_bar vdd vdd PMOS_VTG W=280.0n L=50n m=1
MM11 sel_bar sel vdd vdd PMOS_VTG W=280.0n L=50n m=1
.ENDS

