from modules.shared_decoder.sotfet.config_sotfet_mram import *

from freepdk45_common_config import *

model_file = "sotfet_mram_small_real.scs"
reference_vt = 0.9
ferro_ratio = 0.01
g_AD = 8*0.32
gate_res = 100
fm_temperature = 0
h_ext = 0.002
llg_prescale = 0.001  # prescale internal llg model voltages

sense_amp_ref = 0.8

