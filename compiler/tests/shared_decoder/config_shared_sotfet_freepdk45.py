from modules.shared_decoder.sotfet.config_sotfet_mram import *

from freepdk45_common_config import *

python_path += ["modules/horizontal"]

symmetric_bitcell = False
mirror_bitcell_y_axis = True
mram_bitcell = "mram/sotfet_mram_small"
body_tap = "sotfet_mram_bitcell_tap"
body_tap_mod = "mram/sotfet_mram_small_tap"
tgate_column_mux_mod = "mram/tgate_column_mux_sotfet"

precharge_array = "precharge_reset_array.PrechargeResetArray"

use_x_body_taps = False
use_y_body_taps = True

tgate_column_mux_mod = "mram/tgate_column_mux_sotfet"
sense_amp_mod = "mram/sotfet_sense_amp_mram"
write_driver_mod = "mram/sotfet_write_driver_mram"


model_file = "sotfet_mram_small_real.scs"
reference_vt = 0.9
ferro_ratio = 0.01
g_AD = 8*0.32
gate_res = 100
fm_temperature = 0
h_ext = 0.002
llg_prescale = 0.001  # prescale internal llg model voltages

sense_amp_ref = 0.8

