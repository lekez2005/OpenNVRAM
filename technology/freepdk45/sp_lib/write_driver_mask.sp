************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram
* Top Cell Name: write_driver_mask
* View Name:     schematic
* Netlisted on:  Jan 16 04:17:41 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram
* Cell Name:    write_driver_mask
* View Name:    schematic
************************************************************************

.SUBCKT write_driver_mask bl br data data_bar en en_bar gnd mask_bar vdd
MM14 net61 mask_bar gnd gnd NMOS_VTG W=100n L=50n m=1
MM13 net67 en gnd gnd NMOS_VTG W=500n L=50n m=1
MM7 net61 data_bar gnd gnd NMOS_VTG W=100n L=50n m=1
MM6 br net61 net67 gnd NMOS_VTG W=500n L=50n m=1
MM4 net60 mask_bar gnd gnd NMOS_VTG W=100n L=50n m=1
MM3 net66 en gnd gnd NMOS_VTG W=500n L=50n m=1
MM12 net60 data gnd gnd NMOS_VTG W=100n L=50n m=1
MM0 bl net60 net66 gnd NMOS_VTG W=500n L=50n m=1
MM15 net61 data_bar net63 vdd PMOS_VTG W=300n L=50n m=1
MM10 net62 en_bar vdd vdd PMOS_VTG W=300n L=50n m=1
MM9 br net61 net62 vdd PMOS_VTG W=300n L=50n m=1
MM8 net63 mask_bar vdd vdd PMOS_VTG W=300n L=50n m=1
MM5 net60 data net65 vdd PMOS_VTG W=300n L=50n m=1
MM2 net64 en_bar vdd vdd PMOS_VTG W=300n L=50n m=1
MM1 bl net60 net64 vdd PMOS_VTG W=300n L=50n m=1
MM11 net65 mask_bar vdd vdd PMOS_VTG W=300n L=50n m=1
.ENDS

