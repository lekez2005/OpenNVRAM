import os

python_path = ["modules/sotfet"]

# modules
decoder_flops = False


bitcell = "sf_cam_bitcell"
bitcell_array = "sf_cam_bitcell_array"
wordline_driver = "wordline_driver_array"
ms_flop_array_horizontal = "ms_flop_array_horizontal"
ms_flop_array = "sot_flop_array"
tag_flop_array = "tag_flop_array"
ml_precharge_array = "sf_ml_precharge_array"
ml_precharge = "sf_matchline_precharge"
body_tap = "sot_body_tap"
search_sense_amp_array = "search_sense_amp_array"
predecoder_flop = "ms_flop_horz_pitch"
search_sense_amp = "sot_search_sense_amp"

cells_per_group = 2

logic_buffers_height = 1.2
bitline_buffer_sizes = [3, 8]
clk_buffers = [2, 5.04, 12.7, 32]
clk_bar_buffers = [2, 6, 18]
write_buffers = [3.5, 12]
chb_buffers = [2, 3.632, 6.596, 12]
wordline_en_buffers = [1, 3]
sense_amp_buffers = [2, 4.9, 12]

wordline_buffers = [1]

ml_precharge_size = 6

# cam config
word_size = 64
num_words = 64
num_banks = 2
words_per_row = 1

# simulation
slew_rate = 0.005  # in nanoseconds
c_load = 1  # femto-farads
setup_time = 0.015  # in nanoseconds
feasible_period = 1.8  # in nanoseconds
duty_cycle = 0.35

# temp dir
openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "sotfet_cam")
