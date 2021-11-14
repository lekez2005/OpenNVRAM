from config_cam_freepdk45 import *

python_path = ["modules/mram/sotfet", "modules/cam/sotfet"]

# sotfet simulation config
mram = "sotfet"
reference_vt = 1
ferro_ratio = 1.85
llg_prescale = 0.001

mram_bitcell = "cam/sotfet_scam_cell"
model_file = "mram/sotfet_cell.sp"
schematic_model_file = "cam/sotfet_scam_schematic.sp"
default_model_params = "mram/default_llg_params.py"
bitcell_state_probe = "XI0.state"

sot_2_template = "Xbank{bank}_Xbitcell_array_Xbit_r{row}_c{col}_sot_2_gate"
sot_1_template = "N_Xbank{bank}_Xbitcell_array_Xbit_r{row}_c{col}" \
                 "_sot_1_gate_Xbank{bank}_Xbitcell_array_Xbit_r{row}_c{col}_mm3_d"

bitcell_name_template = "Xbank{bank}_Xbitcell_array_{name}_r{row}_c{col}"
pex_replacement_pattern = r"mXbank(?P<bank>[0-9]+)_Xbitcell_array_(?P<name>\S+)_r(?P<row>" \
                          r"[0-9]+)_c(?P<col>[0-9]+)_mm(?P<tx_num>\S+)"

# bitcell
symmetric_bitcell = False
mirror_bitcell_y_axis = True
bitcell = "sotfet_cam_cell"
# bitcell_mod = "cam/sotfet_cam_cell"
bitcell_mod = "cam/sotfet_scam_cell"
sotfet_mode = "or"
body_tap = "sotfet_mram_bitcell_tap"
body_tap_mod = "cam/sotfet_cam_tap"
bitcell_array = "sotfet_cam_bitcell_array.SotfetCamBitcellArray"
use_y_body_taps = False

precharge = "sotfet_cam_precharge.SotfetCamPrecharge"
# search_sense_amp_mod = "cam/sotfet_ml_latched_sense_amp"
search_sense_amp_mod = "cam/sotfet_ml_sense_amp"
write_driver_mod = "mram/sot_write_driver_mux_buffer"
tgate_column_mux_mod = "mram/tgate_column_mux_sotfet"

control_buffers_class = "sotfet_cam_control_buffers.SotfetCamControlBuffers"
control_buffers_num_rows = 1

ml_buffers = [2.51, 6.32, 15.9, 40]
discharge_buffers = [3.42, 11.7, 40]


def configure_modules(bank, OPTS):
    if OPTS.sotfet_mode == "or":
        OPTS.reference_vt = 1
        OPTS.ferro_ratio = 1.85
    else:
        OPTS.reference_vt = 0.111
        OPTS.ferro_ratio = 0.318


def configure_timing(sram, OPTS):
    num_rows = sram.bank.num_rows
    num_cols = sram.bank.num_cols
    OPTS.sense_trigger_setup = 0.15

    write_settling_time = 1.5

    if num_rows == 16 and num_cols == 64:
        first_read = 0.3
        second_read = 0.6
        OPTS.sense_trigger_delay = second_read - 0.3
        first_write = 0.5
        write_trigger_delay = 0.6
    elif num_rows == 64 and num_cols == 64:
        first_read = 0.3
        second_read = 0.6
        OPTS.sense_trigger_delay = second_read - 0.3
        first_write = 0.5
        write_trigger_delay = 0.6
    elif num_rows == 128 and num_cols == 128:
        first_read = 0.8
        second_read = 1.05
        OPTS.sense_trigger_delay = second_read - 0.3
        first_write = 0.7
        write_trigger_delay = 0.75
    elif num_rows == 256 and num_cols == 128:
        first_read = 1.1
        second_read = 1.5
        OPTS.sense_trigger_delay = second_read - 0.4
        first_write = 1.1
        write_trigger_delay = 1.3
    else:
        assert False, "Timing unspecified for CAM configuration"

    OPTS.write_trigger_delay = write_trigger_delay
    second_write = write_settling_time + OPTS.write_trigger_delay

    return first_read, first_write, second_read, second_write
