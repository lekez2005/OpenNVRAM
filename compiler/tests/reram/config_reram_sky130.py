from config_baseline import *
from sky130_common_config import *
from config_reram_base import *
# from tests.reram.config_reram_base import *

bitcell_tx_size = 7  # bitcell access device size in um
bitcell_tx_mults = 4  # number of access device fingers
bitcell_width = 2.5  # bitcell width in um

symmetric_bitcell = False
mirror_bitcell_y_axis = True
use_x_body_taps = False
use_y_body_taps = True

bitcell_array = "reram_bitcell_array.ReRamBitcellArray"

precharge = "bitline_discharge.BitlineDischarge"
precharge_size = 6

ms_flop = "ms_flop_clk_buf.MsFlopClkBuf"
ms_flop_horz_pitch = "ms_flop_horz_pitch.MsFlopHorzPitch"
sense_amp = "reram_sense_amp.ReRamSenseAmp"
