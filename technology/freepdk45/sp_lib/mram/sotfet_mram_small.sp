.SUBCKT sotfet_mram_small BL BR RWL WWL gnd
MM1 BL RWL sf_source gnd NMOS_VTG W=170n L=50n m=1
MM0 BL WWL vgate_p gnd NMOS_VTG W=340.0n L=50n m=1 nf=2
MM2 sf_source sf_gate_int BR gnd NMOS_VTG W=170n L=50n m=1
.ENDS
