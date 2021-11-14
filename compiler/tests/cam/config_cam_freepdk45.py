from config_baseline import *
from freepdk45_common_config import *
from config_cam_base import *
from config_cam_base import configure_modules as default_configure_modules

bitcell_mod = "cam_cell_6t"
write_driver_mod = "write_driver_mux_buffer"

run_optimizations = False
route_control_signals_left = True

precharge_buffers = [3.42, 11.7, 40]

sense_amp_vref = 0.85


def configure_modules(bank, OPTS):
    default_configure_modules(bank, OPTS)
    if bank.words_per_row > 1:
        OPTS.write_driver_mod = "write_driver_mux_buffer"
    else:
        OPTS.write_driver_mod = "write_driver_mask"


def configure_timing(sram, OPTS):
    num_rows = sram.bank.num_rows
    num_cols = sram.bank.num_cols
    OPTS.sense_trigger_setup = 0.15

    if num_rows == 16 and num_cols == 64:
        first_read = 0.5
        second_read = 0.45
        OPTS.sense_trigger_delay = second_read - 0.2
        first_write = 0.4
        second_write = 0.4
    elif num_rows == 64 and num_cols == 64:
        first_read = 0.6
        second_read = 0.75
        OPTS.sense_trigger_delay = second_read - 0.2
        first_write = 0.5
        second_write = 0.5
    elif num_rows == 128 and num_cols == 128:
        first_read = 1.1
        second_read = 1.5
        OPTS.sense_trigger_delay = second_read - 0.2
        first_write = 1
        second_write = 0.9
    elif num_rows == 256 and num_cols == 128:
        first_read = 1.7
        second_read = 2.1
        OPTS.sense_trigger_delay = second_read - 0.5
        first_write = 1.7
        second_write = 1.5
    else:
        assert False, "Timing unspecified for CAM configuration"
    return first_read, first_write, second_read, second_write
