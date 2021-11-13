.SUBCKT sotfet_scam_cell BL BR ML WL gnd
MM0 sot_1_gate WL sot_2_gate gnd NMOS_VTG W=270.0n L=50n m=2
XI0 ML BL sot_1_gate vmid gnd sotfet
XI1 vmid BR sot_2_gate gnd gnd sotfet
.ENDS
