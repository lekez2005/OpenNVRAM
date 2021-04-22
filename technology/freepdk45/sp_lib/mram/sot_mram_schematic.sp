* sot_mram_small
.SUBCKT sot_mram_small BL BR RWL WWL gnd
*.PININFO RWL:I WWL:I BL:B BR:B gnd:B
MM0 BL WWL sot_p gnd NMOS_VTG w=270.0n l=50n as=5.67e-14 ad=3.78e-14 \
        ps=960.0n pd=280.0n m=2
MM1 BL RWL mtj_top gnd NMOS_VTG w=150.0n l=50n as=1.575e-14 ad=1.575e-14 \
        ps=360.0n pd=360.0n m=1
XI0  mtj_top BR sot_p sot_cell
.ENDS


.SUBCKT sot_mram_ref_small BL BR RWL WWL gnd
*.PININFO RWL:I WWL:I BL:B BR:B gnd:B
MM0 BL WWL sot_p gnd NMOS_VTG w=270.0n l=50n as=5.67e-14 ad=3.78e-14 \
        ps=960.0n pd=280.0n m=2
MM1 BL RWL mtj_top gnd NMOS_VTG w=150.0n l=50n as=1.575e-14 ad=1.575e-14 \
        ps=360.0n pd=360.0n m=1
XI0  mtj_top BR sot_p sot_cell_ref
.ENDS
