.SUBCKT sotfet_mram_small BL BR RWL WWL gnd
MM0 BL WWL sot_p gnd NMOS_VTG W=170.0n L=50n m=2
MM2 BL RWL sf_drain gnd NMOS_VTG W=170.0n L=50n m=1
XI0 sf_drain sot_p BR BR gnd sotfet
.ENDS
