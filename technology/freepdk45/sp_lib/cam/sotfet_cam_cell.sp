************************************************************************
* auCdl Netlist:
* 
* Library Name:  spintronics
* Top Cell Name: sotfet_cam_cell
* View Name:     schematic_for_lvs
* Netlisted on:  Sep  9 22:46:20 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: spintronics
* Cell Name:    sotfet_cam_cell
* View Name:    schematic_for_lvs
************************************************************************

.SUBCKT sotfet_cam_cell BL BR ML WL gnd
MM0 ML BL gnd gnd NMOS_VTG W=200n L=50n m=1
MM2 ML BR gnd gnd NMOS_VTG W=200n L=50n m=1
MM3 sot_1_gate WL sot_2_gate gnd NMOS_VTG W=270.0n L=50n m=2
.ENDS

