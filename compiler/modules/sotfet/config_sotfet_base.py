import os

python_path = ["modules/sotfet"]

# modules
decoder_flops = True


bitcell = "sf_cam_bitcell"
bitcell_array = "sf_cam_bitcell_array"
wordline_driver = "wordline_driver_array"
ms_flop_array_horizontal = "ms_flop_array_horizontal"
ms_flop_array = "ms_flop_array"
tag_flop_array = "tag_flop_array"
ml_precharge_array = "ml_precharge_array"
ml_precharge = "sf_matchline_precharge"
body_tap = "cam_body_tap"
search_sense_amp_array = "search_sense_amp_array"
predecoder_flop = "ms_flop_horz_pitch"


logic_buffers_height = 1.3
bitline_buffer_sizes = [2, 8]
clk_buffers = [2, 6, 18, 32]
clk_bar_buffers = [2, 6, 18]
write_buffers = [4, 12]
chb_buffers = [2, 8]
wordline_en_buffers = [2, 8]
sense_amp_buffers = [2, 8]

wordline_buffers = [1]

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
spice_file = os.path.join(openram_temp, 'temp.sp')
pex_spice = os.path.join(openram_temp, 'pex.sp')
reduced_spice = os.path.join(openram_temp, 'reduced.sp')
gds_file = os.path.join(openram_temp, 'temp.gds')
