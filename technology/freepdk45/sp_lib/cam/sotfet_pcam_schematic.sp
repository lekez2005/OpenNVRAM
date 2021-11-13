.SUBCKT sotfet_cam_cell BL BR ML WL gnd
MM0 sot_1_gate WL sot_2_gate gnd NMOS_VTG W=270.0n L=50n m=2
XI0 ML sot_1_gate BL gnd gnd sotfet
XI1 ML sot_2_gate BR gnd gnd sotfet
.ENDS
