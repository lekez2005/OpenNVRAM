from copy import copy

from modules.shared_decoder.config_shared import *

independent_banks = False

# modules
bitcell = "cam_bitcell"
bitcell_mod = "cam_bitcell"
body_tap_mod = "cam_body_tap"
replica_bitcell = "cam_replica_bitcell"
bitcell_array = "cam_bitcell_array"

ml_precharge = "matchline_precharge.MatchlinePrecharge"
ml_precharge_array = "matchline_precharge_array.MatchlinePrechargeArray"
precharge = "cam_precharge.CamPrecharge"
precharge_array = "cam_precharge_array.CamPrechargeArray"
ml_precharge_size = 4

write_driver_mod = "write_driver_mux_buffer"

search_sense_amp = "search_sense_amp_array.SearchSenseAmp"
search_sense_amp_mod = "ml_sense_amp"
search_sense_amp_array = "search_sense_amp_array.SearchSenseAmpArray"

control_buffers_class = "cam_control_buffers.CamControlBuffers"
wordline_en_buffers = [3.42, 11.7, 40]

ml_buffers = [2.51, 6.32, 15.9, 40]
precharge_buffers = copy(wordline_en_buffers)
discharge_buffers = copy(ml_buffers)

bank_class = "cam_bank.CamBank"
sram_class = "cam.Cam"

# cam config
word_size = 32
num_words = 256
num_banks = 2
words_per_row = 1


def configure_sizes(bank, OPTS):
    if bank.words_per_row > 1:
        OPTS.ml_buffers = [40 ** ((x + 1) / 3) for x in range(3)]
    else:
        OPTS.ml_buffers = [40 ** ((x + 1) / 4) for x in range(4)]
