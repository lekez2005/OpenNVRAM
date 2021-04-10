************************************************************************
* auCdl Netlist:
*
* Library Name:  spintronics
* Top Cell Name: sot_mram_small
* View Name:     schematic_for_lvs
* Netlisted on:  Apr  3 22:13:49 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: spintronics
* Cell Name:    sot_mram_small
* View Name:    schematic_for_lvs
************************************************************************

.SUBCKT sot_mram_small BL BR RWL WWL gnd
*.PININFO RWL:I WWL:I BL:B BR:B gnd:B
MM0 BL WWL sot_left gnd NMOS_VTG W=170.0n L=50n m=2
MM1 BL RWL BR gnd NMOS_VTG W=170.0n L=50n m=1
.ENDS
