from freepdk45_common_config import *
from config_cam_base import *
from config_cam_base import configure_modules as default_configure_modules

bitcell_mod = "cam_cell_6t"
write_driver_mod = "write_driver_mux_buffer"

run_optimizations = False
route_control_signals_left = True

search_ref = 0.85


def configure_modules(bank, OPTS):
    default_configure_modules(bank, OPTS)
    if bank.words_per_row > 1:
        OPTS.write_driver_mod = "write_driver_mux_buffer"
    else:
        OPTS.write_driver_mod = "write_driver_mask"
