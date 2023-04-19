from config_baseline import *
from sky130_common_config import *
from config_reram_base import *

# module parameters
bitcell_tx_size = 7  # bitcell access device size in um
bitcell_tx_mults = 4  # number of access device fingers
bitcell_width = 2.5  # bitcell width in um

symmetric_bitcell = False
mirror_bitcell_y_axis = True
use_x_body_taps = False
use_y_body_taps = True

bitcell_array = "reram_bitcell_array.ReRamBitcellArray"

separate_vdd_wordline = True
wordline_driver = "reram_wordline_driver_array"
high_voltage_wordline = False
decoder = "reram_row_decoder.reram_row_decoder"

precharge = "bitline_discharge.BitlineDischarge"
precharge_size = 6

ms_flop = "ms_flop_clk_buf.MsFlopClkBuf"
ms_flop_horz_pitch = "ms_flop_horz_pitch.MsFlopHorzPitch"
predecoder_flop = "ms_flop_horz_pitch.MsFlopHorzPitch"
control_flop = "ms_flop_horz_pitch.MsFlopHorzPitch"

sense_amp_array = "sense_amp_array"
sense_amp = "reram_sense_amp.ReRamSenseAmp"

separate_vdd_write = True
if separate_vdd_write:
    write_driver_logic_mod = "write_driver_mux_logic"
    write_driver = "write_driver_mux_separate_vdd.WriteDriverMuxSeparateVdd"
    write_driver_array = "write_driver_mask_array"
else:
    write_driver_mod = "write_driver_pgate.WriteDriverPgate"
    write_driver_array = "write_driver_pgate_array.WriteDriverPgateArray"
    write_driver_logic_size = 2.5

write_vdd_rail_height = 0.5
write_driver_buffer_size = 10

column_mux_array = "single_level_column_mux_array"
column_mux = "tgate_column_mux_pgate"

control_optimizer = "reram_control_buffers_optimizer.ReramControlBuffersOptimizer"

br_reset_buffers = [1, 3.42, 11.7, 40]
bl_reset_buffers = [3.1, 9.65, 30]

logic_buffers_height = 4
run_optimizations = True
control_buffers_num_rows = 2
route_control_signals_left = True
shift_control_flops_down = True

add_buffer_repeaters = False

# simulation params
filament_scale_factor = 1e7
min_filament_thickness = 3.3e-9 * filament_scale_factor
max_filament_thickness = 4.9e-9 * filament_scale_factor
vdd_wordline = 2.5
vdd_write = vdd_write_bl = vdd_write_br = 2.4
sense_amp_vclamp = 0.9
sense_amp_vclampp = 1.2
sense_amp_vref = 1

state_probe_node = "Xmem.state_out"

min_wordline_edge_width = 0.1  # for checking that there is sufficient falling edge time


def set_wordline_driver(is_high_voltage, OPTS):
    if is_high_voltage:
        OPTS.wordline_driver = "level_shift_wordline_driver_array.LevelShiftWordlineDriverArray"
    else:
        OPTS.wordline_driver = "reram_wordline_driver_array"


def configure_timing(sram, OPTS):
    num_rows = sram.bank.num_rows
    num_cols = sram.bank.num_cols
    wpr = sram.bank.words_per_row

    OPTS.sense_trigger_setup = 0.1  # extra time to continue enable sense amp past read cycle

    first_read = 0.4156
    second_read = 3

    trigger_delay = second_read - 0.5
    first_write = 0.8
    second_write = 30

    OPTS.sense_amp_vref = 1

    if num_rows == 16 and num_cols == 16:
        first_read, second_read, trigger_delay = 0.5, 5.355, 4.55
        first_write, second_write = 0.45, 7.2
    elif num_rows == 16 and num_cols == 64:
        first_read, second_read, trigger_delay = 0.6, 5.4, 4.5
        first_write, second_write = 0.425, 6.925
    elif num_rows == 64 and num_cols == 64:
        first_read, second_read, trigger_delay = 0.79, 14.3105, 13.15
        first_write, second_write = 0.57, 8.14
    elif num_rows == 128 and num_cols == 128:
        first_read, second_read, trigger_delay = 1.44, 26.7472, 25.48
        first_write, second_write = 0.7, 9.95
    elif num_rows == 128 and num_cols == 256:
        first_read, second_read, trigger_delay = 1.38, 26.3556, 24.64
        first_write, second_write = 0.7, 9.94

    OPTS.sense_trigger_delay = trigger_delay
    new_options = parse_timing_override(OPTS)
    if new_options:
        return new_options[1]
    else:
        return first_read, first_write, second_read, second_write
