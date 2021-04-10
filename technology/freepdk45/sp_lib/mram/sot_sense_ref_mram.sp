************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram_sot
* Top Cell Name: sot_sense_ref_mram
* View Name:     schematic
* Netlisted on:  Apr  6 03:05:35 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram_sot
* Cell Name:    sot_sense_ref_mram
* View Name:    schematic
************************************************************************

.SUBCKT sot_sense_ref_mram bl_zero bl_one en_bar vclamp vref vdd gnd
MM5 vref vclamp bl_zero gnd NMOS_VTG W=200n L=50n m=1
MM4 vref vclamp bl_one gnd NMOS_VTG W=200n L=50n m=1
MM2 net20 en_bar vdd vdd PMOS_VTG W=200n L=50n m=1
MM3 vref vref net20 vdd PMOS_VTG W=200n L=50n m=1
MM1 vref vref net19 vdd PMOS_VTG W=200n L=50n m=1
MM0 net19 en_bar vdd vdd PMOS_VTG W=200n L=50n m=1
.ENDS

