************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram_sot
* Top Cell Name: sot_write_ref_driver_mram
* View Name:     schematic
* Netlisted on:  Apr 16 14:42:19 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram_sot
* Cell Name:    sot_write_ref_driver_mram
* View Name:    schematic
************************************************************************

.SUBCKT sot_write_ref_driver_mram bl br en en_bar gnd vdd
MM20 br gnd net36 gnd NMOS_VTG W=800n L=50n m=1
MM21 net36 en gnd gnd NMOS_VTG W=800n L=50n m=1
MM3 net66 en gnd gnd NMOS_VTG W=800n L=50n m=1
MM0 bl vdd net66 gnd NMOS_VTG W=800n L=50n m=1
MM19 br gnd net040 vdd PMOS_VTG W=1.2u L=50n m=1
MM22 net040 en_bar vdd vdd PMOS_VTG W=1.2u L=50n m=1
MM2 net64 en_bar vdd vdd PMOS_VTG W=1.2u L=50n m=1
MM1 bl vdd net64 vdd PMOS_VTG W=1.2u L=50n m=1
.ENDS

