import os

python_path = ["modules/sotfet", "modules/sotfet/cmos", "modules/sotfet/fast_ramp"]

# modules

slow_ramp = False

bitcell_name_template = "Xbitcell_b{bank}_r{row}_c{col}"

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

bitline_logic = "sot_bitline_logic"
bitline_logic_tap = "sot_bitline_logic_tap"

bitline_buffer = "sf_bitline_buffer.SfBitlineBuffer"
bitline_buffer_tap = "sf_bitline_buffer.SfBitlineBufferTap"

decoder_flops = True
predecoder_flop = "ms_flop"
predecoder_flop_layout = "v"
search_sense_amp = "sot_search_sense_amp"

cells_per_group = 2

logic_buffers_height = 1.2
bitline_buffer_sizes = [3, 8]
clk_buffers = [2, 8, 32]
clk_bar_buffers = [2, 6, 18]
write_buffers = [2, 6, 18]
chb_buffers = [2, 6, 18]
wordline_en_buffers = [1, 3]
sense_amp_buffers = [4, 12]

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


def configure_sizes(bank, OPTS):
    num_rows = bank.num_rows
    num_cols = bank.num_cols
    if num_rows == 32:
        OPTS.clk_buffers = [2, 6, 16]
        OPTS.clk_bar_buffers = [2, 6, 22]
        OPTS.write_buffers = [2, 6, 18]
        OPTS.chb_buffers = [2, 6, 18]
        OPTS.wordline_en_buffers = [2, 6, 18]

    elif num_rows == 64:
        OPTS.clk_buffers = [2, 6, 18]
        OPTS.clk_bar_buffers = [2, 6, 18]
        OPTS.write_buffers = [2, 6, 18]
        OPTS.chb_buffers = [2, 6, 18]
        OPTS.wordline_en_buffers = [2, 6, 18]
    else:
        OPTS.clk_buffers = [3.1, 9.65, 30]
        OPTS.clk_bar_buffers = [3.1, 9.65, 30]
        OPTS.write_buffers = [3.1, 9.65, 30]
        OPTS.chb_buffers = [3.1, 9.65, 30]
        OPTS.wordline_en_buffers = [3.1, 9.65, 30]

    OPTS.sense_amp_buffers = [4, 12]
    OPTS.wordline_buffers = [1, 3.16, 10]

    if num_cols <= 36:
        OPTS.sense_amp_buffers = [2, 6, 18]
        OPTS.wordline_buffers = [5]
    elif num_cols <= 64:
        OPTS.sense_amp_buffers = [2, 6, 18]
        OPTS.wordline_buffers = [1, 3.16, 10]
    else:
        OPTS.sense_amp_buffers = [3.1, 9.7, 30]
        OPTS.wordline_buffers = [1, 4, 16]

    # override wordline if slow ramp
    # if OPTS.slow_ramp:
    #     OPTS.wordline_buffers = [1]


