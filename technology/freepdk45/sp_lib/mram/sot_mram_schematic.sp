* sot_mram_small
.SUBCKT sot_mram_small BL BR RWL WWL gnd
*.PININFO RWL:I WWL:I BL:B BR:B gnd:B
MM0 BL WWL sot_p gnd NMOS_VTG w=340.0n l=50n as=3.57e-14 ad=3.57e-14 \
        ps=550.0n pd=550.0n m=1
MM1 BL RWL mtj_top gnd NMOS_VTG w=170.0n l=50n as=1.785e-14 ad=1.785e-14 \
        ps=380.0n pd=380.0n m=1
XI0  mtj_top BR sot_p sot_cell
.ENDS


.SUBCKT sot_mram_ref_small BL BR RWL WWL gnd
*.PININFO RWL:I WWL:I BL:B BR:B gnd:B
MM0 BL WWL sot_p gnd NMOS_VTG w=340.0n l=50n as=3.57e-14 ad=3.57e-14 \
        ps=550.0n pd=550.0n m=1
MM1 BL RWL mtj_top gnd NMOS_VTG w=170.0n l=50n as=1.785e-14 ad=1.785e-14 \
        ps=380.0n pd=380.0n m=1
XI0  mtj_top BR sot_p sot_cell_ref
.ENDS
