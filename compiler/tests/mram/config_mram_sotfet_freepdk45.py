from mram.config_mram import *
from freepdk45_common_config import *

python_path += ["modules/horizontal"]

symmetric_bitcell = False
mirror_bitcell_y_axis = True
mram_bitcell = "mram/sotfet_mram_small"
body_tap = "sotfet_mram_bitcell_tap"
body_tap_mod = "mram/sotfet_mram_small_tap"
tgate_column_mux_mod = "mram/tgate_column_mux_sotfet"

precharge_array = "precharge_reset_array.PrechargeResetArray"
precharge_size = 6
max_precharge_buffers = 60

use_x_body_taps = False
use_y_body_taps = True

# sense_amp_mod = "mram/sotfet_sense_amp_mram"
sense_amp_mod = "mram/sotfet_discharge_sense_amp"
write_driver_mod = "mram/sot_write_driver_mux_buffer"
# write_driver_mod = "mram/sotfet_write_driver_mram"

decoder = "row_decoder_horizontal"
rwl_driver = "wordline_buffer_array_horizontal"
wwl_driver = "wordline_buffer_array_horizontal"

bank_class = "mram_bank.MramBank"
sram_class = "sotfet_mram.SotfetMram"

route_control_signals_left = True
sense_amp_array = "sense_amp_array"
precharge_bl = True
has_br_reset = True

body_tap = "sotfet_mram_bitcell_tap"
control_buffers_num_rows = 2
route_control_signals_left = True
independent_banks = False

model_file = "mram/sotfet_cell.sp"
schematic_model_file = "mram/sotfet_mram_schematic.sp"
default_model_params = "mram/default_llg_params.py"
bitcell_state_probe = "XI0.state"

llg_prescale = 0.001  # prescale internal llg model voltages


def configure_timing(sram, OPTS):
    num_rows = sram.bank.num_rows
    OPTS.sense_trigger_setup = 0.15

    write_settling_time = 2

    if OPTS.precharge_bl:
        OPTS.sense_amp_vref = 0.85
    else:
        OPTS.sense_amp_vref = 0.4

    if num_rows < 64:
        if OPTS.num_banks == 1:
            first_read = 0.8
            second_read = 0.8
            OPTS.sense_trigger_delay = second_read - 0.25
            OPTS.precharge_trigger_delay = 0.6
            first_write = 0.4
            write_trigger_delay = 0.5
        else:
            OPTS.sense_trigger_delay = 0.6
            OPTS.precharge_trigger_delay = 0.6
            first_read = 0.8
            second_read = 0.8
            first_write = 0.4
            write_trigger_delay = 0.5
    elif num_rows < 128:
        first_read = 0.8
        second_read = 0.8
        OPTS.sense_trigger_delay = second_read - 0.25
        OPTS.precharge_trigger_delay = 0.6
        first_write = 0.4
        write_trigger_delay = 0.75
    else:
        if OPTS.num_banks == 1:
            OPTS.precharge_trigger_delay = 1
            first_read = first_write = 0.9
            second_read = 0.8
            OPTS.sense_trigger_delay = second_read - 0.25
            write_trigger_delay = 1
        else:
            if OPTS.precharge_bl:
                first_read = 1.2
                OPTS.sense_trigger_delay = 0.6
                second_read = OPTS.sense_trigger_delay + 0.2
            else:
                first_read = 0.6
                OPTS.sense_trigger_delay = 1.3
                second_read = OPTS.sense_trigger_delay + 0.3
            first_write = 0.6
            OPTS.precharge_trigger_delay = first_read + 0.1
            write_trigger_delay = 1.2

    OPTS.write_trigger_delay = write_trigger_delay
    second_write = write_settling_time + OPTS.write_trigger_delay

    return first_read, first_write, second_read, second_write
