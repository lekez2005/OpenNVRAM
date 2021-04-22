************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram_sot
* Top Cell Name: write_driver_mux_buffer
* View Name:     schematic
* Netlisted on:  Apr 20 03:39:17 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram_sot
* Cell Name:    write_driver_mux_logic
* View Name:    schematic
************************************************************************

.SUBCKT write_driver_mux_logic bl_n bl_p br_n br_p data data_bar en gnd mask 
+ vdd
MM28 bl_n data gnd gnd NMOS_VTG W=130.0n L=50n m=1
MM25 br_n mask_en_bar gnd gnd NMOS_VTG W=130.0n L=50n m=1
MM22 bl_n mask_en_bar gnd gnd NMOS_VTG W=130.0n L=50n m=1
MM20 br_n data_bar gnd gnd NMOS_VTG W=130.0n L=50n m=1
MM15 net057 mask gnd gnd NMOS_VTG W=200n L=50n m=1
MM14 mask_en_bar en net057 gnd NMOS_VTG W=200n L=50n m=1
MM21 mask_en mask_en_bar gnd gnd NMOS_VTG W=130.0n L=50n m=1
MM23 br_p data_bar net055 gnd NMOS_VTG W=200n L=50n m=1
MM24 net055 mask_en gnd gnd NMOS_VTG W=200n L=50n m=1
MM26 net056 mask_en gnd gnd NMOS_VTG W=200n L=50n m=1
MM27 bl_p data net056 gnd NMOS_VTG W=200n L=50n m=1
MM41 bl_p data vdd vdd PMOS_VTG W=200n L=50n m=1
MM42 bl_p mask_en vdd vdd PMOS_VTG W=200n L=50n m=1
MM39 mask_en mask_en_bar vdd vdd PMOS_VTG W=200n L=50n m=1
MM38 mask_en_bar mask vdd vdd PMOS_VTG W=200n L=50n m=1
MM37 mask_en_bar en vdd vdd PMOS_VTG W=200n L=50n m=1
MM36 br_p data_bar vdd vdd PMOS_VTG W=200n L=50n m=1
MM35 br_p mask_en vdd vdd PMOS_VTG W=200n L=50n m=1
MM34 net054 mask_en_bar vdd vdd PMOS_VTG W=400n L=50n m=1
MM33 bl_n data net054 vdd PMOS_VTG W=400n L=50n m=1
MM32 net053 mask_en_bar vdd vdd PMOS_VTG W=400n L=50n m=1
MM31 br_n data_bar net053 vdd PMOS_VTG W=400n L=50n m=1
.ENDS

************************************************************************
* Library Name: openram_sot
* Cell Name:    write_driver_mux_buffer
* View Name:    schematic
************************************************************************

.SUBCKT write_driver_mux_buffer bl br data data_bar en gnd mask vdd
XI0 bl_n bl_p br_n br_p data data_bar en gnd mask vdd / write_driver_mux_logic
MM0 br br_n gnd gnd NMOS_VTG W=400n L=50n m=1
MM21 bl bl_n gnd gnd NMOS_VTG W=400n L=50n m=1
MM1 br br_p vdd vdd PMOS_VTG W=600n L=50n m=1
MM39 bl bl_p vdd vdd PMOS_VTG W=600n L=50n m=1
.ENDS

