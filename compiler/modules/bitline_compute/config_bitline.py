from modules.bitline_compute.baseline.config_baseline import *

baseline = False

alu_height = 0*15

sense_amp_vref = 0.7

sense_amp_mod = "dual_latched_sense_amp"
sense_amp_tap = "dual_latched_sense_amp_tap"
sense_amp_array = "dual_latched_sense_amp_array"

alu_word_size = 16
alu_cells_per_group = 2

alu_inverter_size = 2

top_level_pex = True

alu_clk_buffer_stages = 3


max_buf_size = 60

logic_buffers_height = 1.4

num_clk_buf_stages = 4
max_clk_buffers = max_buf_size

num_wordline_en_stages = 3
max_wordline_en_buffers = max_buf_size

num_write_en_stages = 4
max_write_buffers = max_buf_size

num_sense_en_stages = 3
max_sense_en_size = max_buf_size

num_precharge_stages = 4
max_precharge_en_size = max_buf_size


buffer_repeater_sizes = [
    ("clk_bar", ["clk_bar"], [10, 20]),
    ("precharge_en_bar", ["precharge_en_bar"], [10, 20]),
    ("write_en", ["write_en_bar", "write_en"], [20, 20]),
    ("sense_en", ["sense_en"], [10, 25]),
    # ("sample_en_bar", ["sample_en_bar"], [10, 20]),

]
