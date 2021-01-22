************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram
* Top Cell Name: ms_flop_horz_pitch
* View Name:     schematic
* Netlisted on:  Jan 19 01:50:27 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram
* Cell Name:    dlatch_clk_clk_bar
* View Name:    schematic
************************************************************************

.SUBCKT dlatch_clk_clk_bar clk clk_bar din dout dout_bar gnd vdd
MM4 int clk_bar din gnd NMOS_VTG W=90n L=50n m=1
MM2 int clk dout gnd NMOS_VTG W=90n L=50n m=1
MM0 dout dout_bar gnd gnd NMOS_VTG W=180.0n L=50n m=1
MM12 dout_bar int gnd gnd NMOS_VTG W=180.0n L=50n m=1
MM5 int clk din vdd PMOS_VTG W=140.0n L=50n m=1
MM3 int clk_bar dout vdd PMOS_VTG W=140.0n L=50n m=1
MM1 dout dout_bar vdd vdd PMOS_VTG W=270.0n L=50n m=1
MM11 dout_bar int vdd vdd PMOS_VTG W=270.0n L=50n m=1
.ENDS

************************************************************************
* Library Name: openram
* Cell Name:    ms_flop_horz_pitch
* View Name:    schematic
************************************************************************

.SUBCKT ms_flop_horz_pitch clk din dout dout_bar gnd vdd
XI1 clk_bar clk_buf mout_bar dout_bar dout gnd vdd / dlatch_clk_clk_bar
XI0 clk_buf clk_bar din mout mout_bar gnd vdd / dlatch_clk_clk_bar
MM1 clk_buf clk_bar gnd gnd NMOS_VTG W=90n L=50n m=2
MM12 clk_bar clk gnd gnd NMOS_VTG W=90n L=50n m=2
MM0 clk_buf clk_bar vdd vdd PMOS_VTG W=425.00n L=50n m=1
MM11 clk_bar clk vdd vdd PMOS_VTG W=135.00n L=50n m=2
.ENDS

