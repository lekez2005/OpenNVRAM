************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram_sot
* Top Cell Name: write_driver_ref_mux_buffer
* View Name:     schematic
* Netlisted on:  Apr 20 03:39:23 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram_sot
* Cell Name:    write_driver_ref_mux_buffer
* View Name:    schematic
************************************************************************

.SUBCKT write_driver_ref_mux_buffer bl br en gnd vdd
MM3 en_bar en vdd vdd PMOS_VTG W=200n L=50n m=1
MM6 br vdd vdd vdd PMOS_VTG W=600n L=50n m=2
MM7 bl en_bar vdd vdd PMOS_VTG W=600n L=50n m=2
MM2 en_bar en gnd gnd NMOS_VTG W=130.0n L=50n m=1
MM4 br en gnd gnd NMOS_VTG W=400n L=50n m=2
MM5 bl gnd gnd gnd NMOS_VTG W=400n L=50n m=2
.ENDS

