from config_shared_sotfet_freepdk45 import *

python_path += ["modules/shared_decoder/sot"]

mram = "sot"

num_reference_cells = 2

mram_bitcell = "mram/sot_mram_small"
ref_bitcell = "mram/sot_mram_ref_small"

model_file = "mram/sot_cell.sp"
ref_model_file = "mram/ref_sot_cell.sp"
schematic_model_file = "mram/sot_mram_schematic.sp"

bitcell_array = "sot_bitcell_array"

precharge_array = "sot_precharge_array.SotPrechargeArray"
precharge_buffers = [1, 20]

column_mux_array = "sot_column_mux_array.SotColumnMuxArray"
tgate_column_mux_mod = "mram/tgate_column_mux_sotfet"
reference_column_mux_mod = "mram/sot_ref_tgate_column_mux"

sense_amp = "sot_sense_amp_array.sot_sense_amp"
sense_amp_ref = "mram/sot_sense_ref_mram"
sense_amp_mod = "mram/sot_sense_amp_mram"
sense_amp_array = "sot_sense_amp_array.SotSenseAmpArray"

write_driver_array = "sot_write_driver_array.SotWriteDriverArray"
# write_driver_ref_mod = "mram/sot_write_ref_driver_mram"

write_driver_ref_mod = "mram/write_driver_ref_mux_buffer"

bank_class = "sot_mram_bank.SotMramBank"
sram_class = "sotfet_mram.SotfetMram"

# sense_amp_vclamp = 0.55
sense_amp_vclamp = 0.55
control_buffers_num_rows = 1


def configure_timing(_, sram, OPTS):
    num_rows = sram.bank.num_rows
    OPTS.sense_trigger_setup = 0.15

    write_settling_time = 1.5

    if num_rows < 64:
        if OPTS.num_banks == 1:
            first_read = 0.8
            second_read = 0.8
            OPTS.sense_trigger_delay = second_read - 0.25
            OPTS.precharge_trigger_delay = 0.6
            first_write = 0.4
            write_trigger_delay = 0.5
        else:
            OPTS.sense_trigger_delay = 0.6
            OPTS.precharge_trigger_delay = 0.6
            first_read = 0.8
            second_read = 0.8
            first_write = 0.4
            write_trigger_delay = 0.5
    elif num_rows < 128:
        first_read = 0.8
        second_read = 0.8
        OPTS.sense_trigger_delay = second_read - 0.25
        OPTS.precharge_trigger_delay = 0.6
        first_write = 0.4
        write_trigger_delay = 0.75
    else:
        if OPTS.num_banks == 1:
            OPTS.precharge_trigger_delay = 1
            first_read = first_write = 0.9
            second_read = 0.8
            OPTS.sense_trigger_delay = second_read - 0.25
            write_trigger_delay = 1
        else:
            OPTS.sense_trigger_delay = 1.8
            OPTS.precharge_trigger_delay = 0.1
            first_write = 0.6
            first_read = 0.6
            second_read = OPTS.sense_trigger_delay + 0.3
            write_trigger_delay = 0.7

    OPTS.write_trigger_delay = write_trigger_delay
    second_write = write_settling_time + OPTS.write_trigger_delay

    return first_read, first_write, second_read, second_write
