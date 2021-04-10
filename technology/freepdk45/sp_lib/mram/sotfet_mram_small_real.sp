************************************************************************
* auCdl Netlist:
* 
* Library Name:  spintronics
* Top Cell Name: sotfet_mram_small
* View Name:     schematic
* Netlisted on:  Mar 22 17:46:25 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM

*.GLOBAL gnd!

*.PIN gnd!

************************************************************************
* Library Name: spintronics
* Cell Name:    p_to_ids
* View Name:    schematic
************************************************************************

.SUBCKT p_to_ids B D S VG p_z
MM0 D vg_nfet S B NMOS_VTG W=200n L=50n m=1
XI2 VG net13 p_z / p_to_vg
.ENDS

************************************************************************
* Library Name: shared_spin
* Cell Name:    m_to_p
* View Name:    schematic
************************************************************************

.SUBCKT m_to_p m_x m_y m_z p_z
*.CONNECT p_z m_z 
.ENDS

************************************************************************
* Library Name: shared_spin
* Cell Name:    sotfet
* View Name:    schematic
************************************************************************

.SUBCKT sotfet B D G_minus G_plus S state
*.CONNECT state mz 
XI8 B D S VG p_z / p_to_ids
RR0 VG G_plus 0.5*gate_R $[RP]
RR1 net28 VG 0.5*gate_R $[RP]
XI6 mx my mz p_z / m_to_p
XI9 gnd! mx my mz phi theta i_x gnd! gnd! / sot_llg
.ENDS

************************************************************************
* Library Name: spintronics
* Cell Name:    sotfet_mram_small
* View Name:    schematic
************************************************************************

.SUBCKT sotfet_mram_small BL BR RWL WWL gnd
MM1 BL RWL net13 gnd NMOS_VTG W=170n L=50n m=1
MM0 BL WWL net12 gnd NMOS_VTG W=340.0n L=50n m=1
XI0 gnd net13 BR net12 BR state / sotfet gate_R=gate_res
.ENDS

