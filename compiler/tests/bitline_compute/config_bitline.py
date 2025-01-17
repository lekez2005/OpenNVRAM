from config_baseline import *

python_path = ["modules/bitline_compute"]

run_optimizations = True
route_control_signals_left = True
control_buffers_num_rows = 1

# temp dir
openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "bitline_compute")

# TODO integrate in configure_timing
sense_trigger_delay = 0.5
sense_trigger_delay_differential = 0.5

baseline = False
top_level_pex = True

sense_amp_vref = 0.7

sense_amp_mod = "dual_latched_sense_amp"
sense_amp_tap = "dual_latched_sense_amp_tap"
sense_amp_array = "dual_latched_sense_amp_array"

alu_word_size = 32
alu_cells_per_group = 2

alu_inverter_size = 2

alu_clk_buffer_stages = 3

buffer_repeater_sizes = [
    ("clk_bar", ["clk_bar"], [10, 20]),
    ("precharge_en_bar", ["precharge_en_bar"], [10, 20]),
    ("write_en", ["write_en_bar", "write_en"], [20, 20]),
    ("sense_en", ["sense_en"], [10, 25]),
    # ("sample_en_bar", ["sample_en_bar"], [10, 20]),
]

bank_class = "bl_bank.BlBank"
control_buffers_class = "bl_latched_control_buffers.LatchedControlBuffers"
control_optimizer = "bl_compute_optimizer.BlComputeOptimizer"
sram_class = "bl_sram.BlSram"


def configure_sense_amps(OPTS):

    if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
        # need large clk_buf to buffer the clk going to the latches
        OPTS.clk_buffers = [1, 5, 20, 60, 65]  # clk_buf drives two sets of latches
        if OPTS.baseline:
            OPTS.sense_amp_mod = "sense_amp"
            OPTS.sense_amp_tap = "sense_amp_tap"
            OPTS.sense_amp_array = "sense_amp_array"
            OPTS.control_buffers_class = \
                "baseline_latched_control_buffers.LatchedControlBuffers"
            OPTS.wordline_en_buffers = [2.83, 8.1, 23, 65]
        else:
            OPTS.sense_amp_mod = "dual_sense_amp"
            OPTS.sense_amp_tap = "dual_sense_amp_tap"
            OPTS.sense_amp_array = "dual_sense_amp_array"
            OPTS.sense_amp_buffers = [1, 7, 50, 60]  # slow down sense_en to avoid glitch
            OPTS.wordline_en_buffers = [1, 2.8, 8, 25, 65 ]  # make wordline en faster
            OPTS.control_buffers_class = \
                "bl_mirrored_control_buffers.BlMirroredControlBuffers"

        OPTS.precharge_buffers = [1, 3.9, 15, 60]
    else:
        OPTS.clk_buffers = [1, 5, 20, 65, 30]  # clk only used by decoders (no latches)
        OPTS.sampleb_buffers = [1, 3.7, 13.6, 50]

        if OPTS.baseline:
            OPTS.sense_amp_mod = "latched_sense_amp"
            OPTS.sense_amp_tap = "latched_sense_amp_tap"
            OPTS.sense_amp_array = "sense_amp_array"
            OPTS.sense_amp_buffers = [3.56, 12.6, 45]
            OPTS.tri_en_buffers = [3.42, 11.7, 40, 40]
            OPTS.precharge_buffers = [1, 3.9, 15, 60]
            OPTS.precharge_size = 1.5
            OPTS.control_buffers_class = \
                "baseline_latched_control_buffers.LatchedControlBuffers"
        else:
            OPTS.sense_amp_mod = "dual_latched_sense_amp"
            OPTS.sense_amp_tap = "dual_latched_sense_amp_tap"
            OPTS.sense_amp_array = "dual_latched_sense_amp_array"
            OPTS.sense_amp_buffers = [3.56, 12.6, 45]
            OPTS.wordline_en_buffers = [2.83, 8.1, 23, 65]  # make wordline en faster

            OPTS.precharge_buffers = [1, 3.9, 15, 60]
            OPTS.sense_precharge_buffers = [1, 3.1, 9.6, 30]
            OPTS.precharge_size = 1.5

            OPTS.control_buffers_class = \
                "bl_latched_control_buffers.LatchedControlBuffers"


def configure_modules(bank, OPTS):
    configure_sense_amps(OPTS)
    if OPTS.serial:
        OPTS.sr_clk_buffers = [1, 3.53, 12.5, 44]
        OPTS.sram_class = "bs_sram.BsSram"
    else:
        OPTS.sr_clk_buffers = [1, 6.6, 44]
        OPTS.sram_class = "bl_sram.BlSram"
