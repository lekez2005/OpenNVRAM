************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram_sot
* Top Cell Name: sotfet_write_driver_mram
* View Name:     schematic
* Netlisted on:  Mar 27 21:02:38 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram_sot
* Cell Name:    sotfet_write_driver_mram
* View Name:    schematic
************************************************************************

.SUBCKT sotfet_write_driver_mram bl br data data_bar en en_bar gnd mask_bar vdd
MM14 br_bar mask_bar gnd gnd NMOS_VTG W=180.0n L=50n m=1
MM13 net67 en gnd gnd NMOS_VTG W=800n L=50n m=1
MM7 br_bar data_bar gnd gnd NMOS_VTG W=180.0n L=50n m=1
MM6 br br_bar net67 gnd NMOS_VTG W=800n L=50n m=1
MM4 bl_bar mask_bar gnd gnd NMOS_VTG W=180.0n L=50n m=1
MM3 net66 en gnd gnd NMOS_VTG W=800n L=50n m=1
MM12 bl_bar data gnd gnd NMOS_VTG W=180.0n L=50n m=1
MM0 bl bl_bar net66 gnd NMOS_VTG W=800n L=50n m=1
MM15 br_bar data_bar net63 vdd PMOS_VTG W=540.0n L=50n m=1
MM10 net62 en_bar vdd vdd PMOS_VTG W=1.2u L=50n m=1
MM9 br br_bar net62 vdd PMOS_VTG W=1.2u L=50n m=1
MM8 net63 mask_bar vdd vdd PMOS_VTG W=540.0n L=50n m=1
MM5 bl_bar data net65 vdd PMOS_VTG W=540.0n L=50n m=1
MM2 net64 en_bar vdd vdd PMOS_VTG W=1.2u L=50n m=1
MM1 bl bl_bar net64 vdd PMOS_VTG W=1.2u L=50n m=1
MM11 net65 mask_bar vdd vdd PMOS_VTG W=540.0n L=50n m=1
.ENDS

