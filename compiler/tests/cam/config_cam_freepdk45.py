from config_baseline import *
from freepdk45_common_config import *
from config_cam_base import *
from config_cam_base import configure_modules as default_configure_modules

bitcell_mod = "cam_cell_6t"
write_driver_mod = "write_driver_mux_buffer"

run_optimizations = False
route_control_signals_left = True

sense_amp_vref = 0.85


def configure_modules(bank, OPTS):
    default_configure_modules(bank, OPTS)
    if bank.words_per_row > 1:
        OPTS.write_driver_mod = "write_driver_mux_buffer"
    else:
        OPTS.write_driver_mod = "write_driver_mask"


def configure_timing(sram, OPTS):
    from config_20_freepdk45 import configure_timing as default_configure_timing
    timing = default_configure_timing(sram, OPTS)
    first_read, first_write, second_read, second_write = timing
    return timing
