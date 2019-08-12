import optparse
import os

class options(optparse.Values):
    """
    Class for holding all of the OpenRAM options. All of these options can be over-riden in a configuration file
    that is the sole required command-line positional argument for openram.py.
    """

    # This is the technology directory.
    openram_tech = ""
    # This is the name of the technology.
    tech_name = ""
    # This is the temp directory where all intermediate results are stored.
    openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "openram_temp")
    # openram_temp = os.environ["SCRATCH"] + "/openram/openram_{0}_temp/".format(os.getpid())

    spice_file = os.path.join(openram_temp, 'temp.sp')
    pex_spice = os.path.join(openram_temp, 'pex.sp')
    reduced_spice = os.path.join(openram_temp, 'reduced.sp')
    gds_file = os.path.join(openram_temp, 'temp.gds')


    # This is the verbosity level to control debug information. 0 is none, 1
    # is minimal, etc.
    debug_level = 0
    # This determines whether  LVS and DRC is checked for each submodule.
    check_lvsdrc = True
    # Variable to select the variant of spice
    spice_name = ""
    # Should we print out the banner at startup
    print_banner = True
    # The DRC/LVS/PEX executable being used which is derived from the user PATH.
    drc_exe = None
    lvs_exe = None
    pex_exe = None
    # The spice executable being used which is derived from the user PATH.
    spice_exe = ""
    # Run with extracted parasitics
    use_pex = False
    # Remove noncritical memory cells for characterization speed-up
    trim_netlist = True
    # Use detailed LEF blockages
    detailed_blockages = True
    # Define the output file paths
    output_path = "."
    # Define the output file base name
    output_name = ""
    # Use analytical delay models by default rather than (slow) characterization
    analytical_delay = True
    # Purge the temp directory after a successful run (doesn't purge on errors, anyhow)
    purge_temp = False

    # These are the configuration parameters
    rw_ports = 1
    r_ports = 0
    # These will get initialized by the the file
    supply_voltages = ""
    temperatures = ""
    process_corners = ""
    use_body_taps = True  # bitcell does not include body taps so insert body taps between bitcells

    spectre_format = "psfbin"
    decoder_flops = False
    

    # These are the default modules that can be over-riden
    decoder = "hierarchical_decoder"
    col_decoder = "column_decoder"
    ms_flop = "ms_flop"
    ms_flop_array = "ms_flop_array"
    ms_flop_array_horizontal = "ms_flop_array_horizontal"
    ms_flop_horz_pitch = "ms_flop_horz_pitch"
    dff = "dff"
    dff_array = "dff_array"
    control_logic = "control_logic"
    bitcell_array = "bitcell_array"
    sense_amp = "sense_amp"
    sense_amp_mod = "sense_amp"
    sense_amp_array = "sense_amp_array"
    precharge_array = "precharge_array"
    column_mux_array = "single_level_column_mux_array"
    write_driver = "write_driver"
    write_driver_array = "write_driver_array"
    tri_gate = "tri_gate"
    tri_gate_array = "tri_gate_array"
    wordline_driver = "wordline_driver"
    replica_bitline = "replica_bitline"
    replica_bitcell = "replica_bitcell"
    bitcell = "bitcell"
    delay_chain = "delay_chain"
    body_tap = "body_tap"

    # buffer stages
    control_logic_clk_buffer_stages = [2, 6, 16, 24]  # buffer stages for control logic clk_bar and clk_buf
    control_logic_logic_buffer_stages = [2.5, 8]  # buffer stages for control logic outputs except clks
    bank_gate_buffers = {  # buffers for bank gate. "default" used for unspecified signals
        "default": [2, 4, 8],
        "clk": [2, 6, 12, 24, 24]
    }
    precharge_size = 2
    column_mux_size = 4

    cells_per_group = 1

