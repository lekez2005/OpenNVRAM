import os

python_path = ["modules/bitline_compute", "modules/bitline_compute/baseline"]

baseline = True

# modules
decoder_flops = True
separate_vdd = False

write_driver_mod = "write_driver_mask_3x"
write_driver_tap = "write_driver_tap"
write_driver_tap_mod = "write_driver_mask_3x_tap"
write_driver_array = "write_driver_mask_array"
wordline_driver = "wordline_driver_array"

data_in_flop = "ms_flop_clk_buf"
data_in_flop_tap = "ms_flop_clk_buf_tap"

# data_in_flop = "ms_flop"
# data_in_flop_tap = "ms_flop_tap"

control_flop = "ms_flop_horz_pitch"

sense_amp_mod = "latched_sense_amp"
sense_amp_tap = "latched_sense_amp_tap"
sense_amp_array = "latched_sense_amp_array"

run_optimizations = False

logic_buffers_height = 1.4

precharge_size = 1  # turns out 1 gives minimum delay in standalone characterization in precharge_optimizer.py

num_buffers = 5

max_buf_size = 60

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

num_wordline_driver_stages = 3
max_wordline_buffers = 20

num_predecoder_stages = 1
max_predecoder_inv_size = 20
max_predecoder_nand = 1.2


wordline_buffers = [1, 4, 16]
predecode_sizes = [1.2, 4]


write_buffers = [1, 5, 25, 50, 65]
precharge_buffers = [1, 3.9, 15, 60]
wordline_en_buffers = [1, 3.9, 15, 45]


sense_amp_buffers = [1, 4.24, 18]

control_flop_buffers = [4]

# cam config
word_size = 64
num_words = 64
num_banks = 1
words_per_row = 1

# simulation
slew_rate = 0.005  # in nanoseconds
c_load = 1  # femto-farads
setup_time = 0.015  # in nanoseconds
feasible_period = 1.8  # in nanoseconds
duty_cycle = 0.35

sense_trigger_delay = 0.5
sense_trigger_delay_differential = 0.5

# temp dir
openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "bl_sram")

# schematic simulation's positive feedback loop may be hard to break
buffer_repeater_sizes = [
    ("clk_bar", ["clk_buf", "clk_bar"], [20, 20]),
    ("sense_en", ["sense_en"], [5, 15]),
    ("write_en", ["write_en_bar", "write_en"], [20, 20]),
    # ("sample_en_bar", ["sample_en_bar"], [5, 15]),
    ("tri_en", ["tri_en_bar", "tri_en"], [10, 10]),
    ("precharge_en_bar", ["precharge_en_bar"], [10, 20]),
]


def configure_sense_amps(sense_amp_type):
    from globals import OPTS

    OPTS.sense_amp_type = sense_amp_type

    if sense_amp_type == OPTS.MIRROR_SENSE_AMP:
        # need large clk_buf to buffer the clk going to the latches
        OPTS.clk_buffers = [1, 5, 20, 60, 65]  # clk_buf drives two sets of latches
        if OPTS.baseline:
            OPTS.sense_amp = "sense_amp"
            OPTS.sense_amp_tap = "sense_amp_tap"
            OPTS.sense_amp_array = "sense_amp_array"
        else:
            OPTS.sense_amp = "dual_sense_amp"
            OPTS.sense_amp_tap = "dual_sense_amp_tap"
            OPTS.sense_amp_array = "dual_sense_amp_array"

        OPTS.precharge_buffers = [1, 3.9, 15, 60]
        OPTS.sense_amp_buffers = [1, 7, 50, 60]  # slow down sense_en to avoid glitch
        OPTS.wordline_en_buffers = [1, 3, 9, 25, 65]  # make wordline en faster
    else:
        OPTS.clk_buffers = [1, 5, 20, 65, 30]  # clk only used by decoders (no latches)
        OPTS.sampleb_buffers = [1, 3.7, 13.6, 50]

        if OPTS.baseline:
            OPTS.sense_amp_mod = "latched_sense_amp"
            OPTS.sense_amp_tap = "latched_sense_amp_tap"
            OPTS.sense_amp_array = "latched_sense_amp_array"
            OPTS.sense_amp_buffers = [3.56, 12.6, 45]
            OPTS.tri_en_buffers = [3.42, 11.7, 40, 40]
            OPTS.precharge_buffers = [1, 3.9, 15, 60]
            OPTS.precharge_size = 1.5
        else:
            OPTS.sense_amp_mod = "dual_latched_sense_amp"
            OPTS.sense_amp_tap = "dual_latched_sense_amp_tap"
            OPTS.sense_amp_array = "dual_latched_sense_amp_array"
            OPTS.sense_amp_buffers = [3.56, 12.6, 45]

            OPTS.precharge_buffers = [1, 3.9, 15, 60]
            OPTS.sense_precharge_buffers = [1, 3.1, 9.6, 30]
            OPTS.precharge_size = 1.5

            if OPTS.serial:
                OPTS.sr_clk_buffers = [1, 3.53, 12.5, 44]
            else:
                OPTS.sr_clk_buffers = [1, 6.6, 44]


