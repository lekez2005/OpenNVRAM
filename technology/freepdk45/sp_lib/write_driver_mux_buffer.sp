************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram
* Top Cell Name: write_driver_mux_buffer
* View Name:     schematic
* Netlisted on:  Apr 23 18:37:05 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram
* Cell Name:    write_driver_mux_logic
* View Name:    schematic
************************************************************************

.SUBCKT write_driver_mux_logic bl_n bl_p br_n br_p data data_bar en gnd mask 
+ vdd
MM19 bl_n data gnd gnd NMOS_VTG W=130.0n L=50n m=1
MM14 br_n mask_en_bar gnd gnd NMOS_VTG W=130.0n L=50n m=1
MM15 bl_n mask_en_bar gnd gnd NMOS_VTG W=130.0n L=50n m=1
MM16 br_n data_bar gnd gnd NMOS_VTG W=130.0n L=50n m=1
MM1 net057 mask gnd gnd NMOS_VTG W=200n L=50n m=1
MM2 mask_en_bar en net057 gnd NMOS_VTG W=200n L=50n m=1
MM4 mask_en mask_en_bar gnd gnd NMOS_VTG W=130.0n L=50n m=1
MM11 br_p data_bar net055 gnd NMOS_VTG W=200n L=50n m=1
MM10 net055 mask_en gnd gnd NMOS_VTG W=200n L=50n m=1
MM8 net056 mask_en gnd gnd NMOS_VTG W=200n L=50n m=1
MM9 bl_p data net056 gnd NMOS_VTG W=200n L=50n m=1
MM6 bl_p data vdd vdd PMOS_VTG W=200n L=50n m=1
MM12 bl_p mask_en vdd vdd PMOS_VTG W=200n L=50n m=1
MM5 mask_en mask_en_bar vdd vdd PMOS_VTG W=200n L=50n m=1
MM3 mask_en_bar mask vdd vdd PMOS_VTG W=200n L=50n m=1
MM0 mask_en_bar en vdd vdd PMOS_VTG W=200n L=50n m=1
MM7 br_p data_bar vdd vdd PMOS_VTG W=200n L=50n m=1
MM13 br_p mask_en vdd vdd PMOS_VTG W=200n L=50n m=1
MM21 net054 mask_en_bar vdd vdd PMOS_VTG W=400n L=50n m=1
MM20 bl_n data net054 vdd PMOS_VTG W=400n L=50n m=1
MM18 net053 mask_en_bar vdd vdd PMOS_VTG W=400n L=50n m=1
MM17 br_n data_bar net053 vdd PMOS_VTG W=400n L=50n m=1
.ENDS

************************************************************************
* Library Name: openram
* Cell Name:    write_driver_mux_buffer
* View Name:    schematic
************************************************************************

.SUBCKT write_driver_mux_buffer bl br data data_bar en gnd mask vdd
MM0 br br_n gnd gnd NMOS_VTG W=600n L=50n m=1
MM3 bl bl_n gnd gnd NMOS_VTG W=600n L=50n m=1
MM1 br br_p vdd vdd PMOS_VTG W=900n L=50n m=1
MM2 bl bl_p vdd vdd PMOS_VTG W=900n L=50n m=1
XI0 bl_n bl_p br_n br_p data data_bar en gnd mask vdd / write_driver_mux_logic
.ENDS

