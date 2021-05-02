simulator lang=spectre

// Library name: shared_spin
// Cell name: sot_cell
// View name: schematic
subckt sot_cell_ref mtj_top sot_p sot_n
parameters sot_R={sot_R} Rp={Rp} spin_pol={spin_pol} spin_wave={spin_wave} tmr_v0={tmr_v0} \
        TI_Lx={TI_Lx} TI_Lz={TI_Lz} alpha={alpha} g_FL={g_FL} g_AD={g_AD} Ms={Ms} \
        Ku={Ku} Hk_x=0 Hk_y=0 Hk_z=1 llg_prescale={llg_prescale} \
        Hext_x=0 Hext_y={H_ext} Hext_z=0 Nxx={Nxx} Nyy={Nyy} \
        Nzz={Nzz} Fm_Lx={Fm_Lx} Fm_Ly={Fm_Ly} Fm_Lz={Fm_Lz}

    VIY (net06 sot_p) vsource dc=0 type=dc
    R0 (vmid sot_n) resistor r=0.5*sot_R
    R1 (net06 vmid) resistor r=0.5*sot_R
    I6 (mtj_top vmid state) tmr_resistance Rp=Rp spin_pol=spin_pol \
        spin_wave=spin_wave v_h=tmr_v0
    H0 (i_x 0) ccvs rm=1p/(TI_Lx*TI_Lz) type=ccvs probe=VIY
    I0 (i_x 0 0 mx my state theta phi 0) sot_llg alpha=alpha g_FL=g_FL \
        g_AD=g_AD Ms=Ms K=Ku d=Fm_Lz Hk_x=Hk_x Hk_y=Hk_y Hk_z=Hk_z \
        Hext_x=Hext_x Hext_y=Hext_y Hext_z=Hext_z Nxx=Nxx Nyy=Nyy Nzz=Nzz \
        prescale=llg_prescale Lx=Fm_Lx Ly=Fm_Ly
ends sot_cell
