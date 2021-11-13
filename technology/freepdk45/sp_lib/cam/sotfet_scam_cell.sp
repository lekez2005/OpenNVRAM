************************************************************************
* auCdl Netlist:
* 
* Library Name:  spintronics
* Top Cell Name: sotfet_scam_cell
* View Name:     schematic_for_lvs
* Netlisted on:  Sep 14 11:43:56 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: spintronics
* Cell Name:    sotfet_scam_cell
* View Name:    schematic_for_lvs
************************************************************************

.SUBCKT sotfet_scam_cell BL BR ML WL gnd
MM0 ML BL vmid gnd NMOS_VTG W=200n L=50n m=1
MM2 gnd BR vmid gnd NMOS_VTG W=200n L=50n m=1
MM3 sot_1_gate WL sot_2_gate gnd NMOS_VTG W=270.0n L=50n m=2
.ENDS

