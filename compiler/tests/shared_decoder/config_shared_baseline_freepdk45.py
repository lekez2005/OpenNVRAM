from modules.shared_decoder.config_shared import *

from freepdk45_common_config import *

setup_time = 0.04  # in nanoseconds
precharge_size = 6
max_precharge_buffers = 60

use_precharge_trigger = True

def configure_timing(_, sram, OPTS):
    num_rows = sram.bank.num_rows
    OPTS.sense_trigger_setup = 0.15
    if num_rows <= 64:
        if OPTS.num_banks == 1:
            first_read = 0.5
            second_read = 0.7
            OPTS.sense_trigger_delay = second_read - 0.25
            OPTS.precharge_trigger_delay = 0.6
            first_write = 0.4
            second_write = 0.9
        else:
            OPTS.sense_trigger_delay = 0.6
            OPTS.precharge_trigger_delay = 0.6
            first_read = 0.5
            second_read = 0.7
            first_write = 0.4
            second_write = 0.9
    else:
        if OPTS.num_banks == 1:
            OPTS.precharge_trigger_delay = 1
            first_read = first_write = 0.9
            second_read = 0.8
            OPTS.sense_trigger_delay = second_read - 0.25
            second_write = 1.5
        else:
            OPTS.sense_trigger_delay = 0.5
            OPTS.precharge_trigger_delay = 0.1
            first_read = first_write = 0.6
            second_read = 0.6
            second_write = 0.6

    return first_read, first_write, second_read, second_write
