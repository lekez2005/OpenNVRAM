bitcell_mod = "cell_6t_4_fingers"
use_body_taps = False

write_driver_mod = "write_driver_no_mask"
sense_amp_array = "latched_sense_amp_array"
tri_gate_mod = "tri_state_buf"
ms_flop_mod = "ms_flop_clk_buf"

logic_buffers_height = 1.35
tech_name = "freepdk45"
process_corners = ["TT"]
supply_voltages = [1.0]
temperatures = [25]

nestlvl = 2

# technology
analytical_delay = False
spice_name = "spectre"
tran_options = " errpreset=moderate "
spectre_command_options = " +aps "
