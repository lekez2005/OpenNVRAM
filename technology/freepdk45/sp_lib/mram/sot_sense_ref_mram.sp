************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram_sot
* Top Cell Name: sot_sense_ref_mram
* View Name:     schematic
* Netlisted on:  Apr 16 14:49:28 2021
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

.SUBCKT sot_sense_ref_mram bl en_bar gnd vclamp vdd vref
MM5 vref vclamp bl gnd NMOS_VTG W=200n L=50n m=1
MM4 vref vclamp bl gnd NMOS_VTG W=200n L=50n m=1
MM2 net20 en_bar vdd vdd PMOS_VTG W=200n L=50n m=1
MM3 vref vref net20 vdd PMOS_VTG W=200n L=50n m=1
MM1 vref vref net19 vdd PMOS_VTG W=200n L=50n m=1
MM0 net19 en_bar vdd vdd PMOS_VTG W=200n L=50n m=1
.ENDS

