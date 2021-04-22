simulator lang=spectre

include "$CADENCE_WORK_DIR/shared_spin/sot_llg/spectre/spectre.scs"
ahdl_include "$CADENCE_WORK_DIR/shared_spin/p_to_vg/veriloga/veriloga.va"
include "$CADENCE_WORK_DIR/shared_spin/p_to_vg/model_params/{tech_name}/p_to_vg.scs"


// Library name: spintronics
// Cell name: p_to_ids
// View name: schematic
subckt p_to_ids B D S VG p_z
parameters delta_vt=0 reference_vt=130.00m ferro_ratio=0.5
    M0 (D vg_nfet S B) NMOS_VTG w=200n l=50n as=2.1e-14 ad=2.1e-14 \
        ps=410.0n pd=410.0n m=1
    V0 (vg_nfet net13) vsource dc=delta_vt type=dc
    I2 (p_z VG net13) p_to_vg reference_vt=reference_vt \
        ferro_ratio=ferro_ratio
ends p_to_ids
// End of subcircuit definition.

// Library name: shared_spin
// Cell name: m_to_p
// View name: schematic
subckt m_to_p m_x m_y m_z p_z
    I2 (m_z p_z) iprobe
ends m_to_p
// End of subcircuit definition.

// Library name: shared_spin
// Cell name: sotfet
// View name: schematic
subckt sotfet D sot_p sot_n S B
parameters delta_vt=0 reference_vt={reference_vt} ferro_ratio={ferro_ratio} sot_R={sot_R}  \
        TI_Lx={TI_Lx} TI_Lz={TI_Lz} alpha={alpha} g_FL={g_FL} g_AD={g_AD} Ms={Ms}  \
        Ku={Ku} Hk_x=0 Hk_y=0 Hk_z=1 llg_prescale={llg_prescale} \
        Hext_x=0 Hext_y={H_ext} Hext_z=0 Nxx={Nxx} Nyy={Nyy} \
        Nzz={Nzz} Fm_Lx={Fm_Lx} Fm_Ly={Fm_Ly} Fm_Lz={Fm_Lz}
    I8 (B D S VG p_z) p_to_ids delta_vt=delta_vt reference_vt=reference_vt \
        ferro_ratio=ferro_ratio
    VIY (net28 sot_p) vsource dc=0 type=dc
    H0 (i_x 0) ccvs rm=1p/(TI_Lx*TI_Lz) type=ccvs probe=VIY
    R0 (VG sot_n) resistor r=0.5*sot_R
    R1 (net28 VG) resistor r=0.5*sot_R
    I6 (mx my mz p_z) m_to_p
    I7 (mz state) iprobe
    I0 (i_x 0 0 mx my mz theta phi 0) sot_llg alpha=alpha g_FL=g_FL \
        g_AD=g_AD Ms=Ms K=Ku d=Fm_Lz Hk_x=Hk_x Hk_y=Hk_y Hk_z=Hk_z \
        Hext_x=Hext_x Hext_y=Hext_y Hext_z=Hext_z Nxx=Nxx Nyy=Nyy Nzz=Nzz \
        prescale=llg_prescale Lx=Fm_Lx Ly=Fm_Ly
ends sotfet
// End of subcircuit definition.
