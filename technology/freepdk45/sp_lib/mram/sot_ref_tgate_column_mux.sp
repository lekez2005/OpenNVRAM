************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram_sot
* Top Cell Name: sot_ref_tgate_column_mux
* View Name:     schematic
* Netlisted on:  Apr 16 15:35:02 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram_sot
* Cell Name:    sot_ref_tgate_column_mux
* View Name:    schematic
************************************************************************

.SUBCKT sot_ref_tgate_column_mux bl<0> bl<1> br<0> br<1> bl_out br_out gnd vdd
MM10 br_out vdd br<1> gnd NMOS_VTG W=800n L=50n m=1
MM9 bl_out vdd bl<1> gnd NMOS_VTG W=800n L=50n m=1
MM5 br_out vdd br<0> gnd NMOS_VTG W=800n L=50n m=1
MM2 bl_out vdd bl<0> gnd NMOS_VTG W=800n L=50n m=1
MM3 bl_out gnd bl<0> vdd PMOS_VTG W=1.2u L=50n m=1
MM4 br_out gnd br<0> vdd PMOS_VTG W=1.2u L=50n m=1
MM8 bl_out gnd bl<1> vdd PMOS_VTG W=1.2u L=50n m=1
MM7 br_out gnd br<1> vdd PMOS_VTG W=1.2u L=50n m=1
.ENDS

