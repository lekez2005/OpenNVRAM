from tests.config_baseline import *
python_path = ["modules/mram/sotfet"]

mram = "sotfet"

llg_prescale = 0.001

cells_per_group = 2

cache_optimization_prefix = "mram_"

bitcell_name_template = "Xbank{bank}_Xbitcell_array_{name}_r{row}_c{col}"
pex_replacement_pattern = r"mXbank(?P<bank>[0-9]+)_Xbitcell_array_(?P<name>\S+)_r(?P<row>[0-9]+)_c(?P<col>[0-9]+)_mm(?P<tx_num>\S+)"

bitcell = "sotfet_mram_bitcell"
mram_bitcell = "sotfet_mram_small"
body_tap_mod = "sotfet_mram_tap_small"
bitcell_array = "sotfet_mram_bitcell_array"

precharge = "sotfet_mram_precharge"
precharge_array = "sotfet_mram_precharge_array"
br_precharge_array = "sotfet_mram_br_precharge_array"
precharge_num_fingers = 3

sense_amp_array = "sotfet_mram_sense_amp_array"
sense_amp_mod = "sotfet_mram_sense_amp"
sense_amp_tap = "sotfet_mram_sense_amp_tap"

decoder = "stacked_hierarchical_decoder"
rwl_driver = "stacked_wordline_driver_array"
wwl_driver = "stacked_wordline_driver_array"

wordline_beta = [1, 0.9, 2.2]  # critical path is for Low to High

num_write_en_stages = 3
write_buffers = [3.56, 12.6, 45]
sense_en_bar_buffers = [3.56, 12.6, 45]

br_reset_buffers = [3.1, 9.65, 30]
bl_reset_buffers = [3.1, 9.65, 30]

num_wordline_en_stages = 3

wwl_en_buffers = [3.56, 12.6, 45]
rwl_en_buffers = [3.56, 12.6, 45]

wwl_buffers = [1, 5, 20]
rwl_buffers = [1, 5, 20]


def configure_modules(bank, OPTS):
    num_rows = bank.num_rows
    num_cols = bank.num_cols

    if num_rows >= 256:
        OPTS.precharge_size = 8
    else:
        OPTS.precharge_size = 5

    if num_rows > 127:
        OPTS.max_wordline_en_buffers = 60
    else:
        OPTS.max_wordline_en_buffers = 30

    if num_cols < 100:
        OPTS.num_clk_buf_stages = 4
        OPTS.num_write_en_stages = 3
        OPTS.max_clk_buffers = 40
        OPTS.max_write_buffers = 40
        # OPTS.tri_en_buffers = [, 11.7, 40, 40]
    else:
        OPTS.num_clk_buf_stages = 5
        OPTS.num_write_en_stages = 5
        OPTS.max_clk_buffers = 60
        OPTS.max_write_buffers = 60
        OPTS.tri_en_buffers = [3.42, 11.7, 40, 40]
