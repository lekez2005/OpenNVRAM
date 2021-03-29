************************************************************************
* auCdl Netlist:
* 
* Library Name:  openram_sot
* Top Cell Name: sotfet_sense_amp_mram
* View Name:     schematic
* Netlisted on:  Mar 27 20:31:17 2021
************************************************************************

*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: openram
* Cell Name:    inv_en
* View Name:    schematic
************************************************************************

.SUBCKT inv_en GND VDD VIN VOUT en
MM0 net11 en GND GND NMOS_VTG W=200n L=50n m=1
MM1 VOUT VIN net11 GND NMOS_VTG W=200n L=50n m=1
MM2 VOUT VIN VDD VDD PMOS_VTG W=200n L=50n m=1
.ENDS

************************************************************************
* Library Name: openram_sot
* Cell Name:    sotfet_sense_amp_mram
* View Name:    schematic
************************************************************************

.SUBCKT sotfet_sense_amp_mram bl dout dout_bar en gnd sampleb vdd vref
XI0 gnd vdd out_int outb_int en / inv_en
XI1 gnd vdd outb_int out_int en / inv_en
MM14 dout_bar out_int gnd gnd NMOS_VTG W=150.0n L=50n m=2
MM12 dout outb_int gnd gnd NMOS_VTG W=150.0n L=50n m=2
MM2 out_int sampleb bl vdd PMOS_VTG W=200n L=50n m=1
MM0 outb_int sampleb vref vdd PMOS_VTG W=200n L=50n m=1
MM11 dout outb_int vdd vdd PMOS_VTG W=225.00n L=50n m=2
MM13 dout_bar out_int vdd vdd PMOS_VTG W=225.00n L=50n m=2
.ENDS

