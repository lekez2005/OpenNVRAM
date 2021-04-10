from config_shared_sotfet_freepdk45 import *

python_path += ["modules/shared_decoder/sot"]

mram = "sot"

num_reference_cells = 2

mram_bitcell = "mram/sot_mram_small"
bitcell_array = "sot_bitcell_array"

precharge_array = "sot_precharge_array.SotPrechargeArray"
column_mux_array = "sot_column_mux_array.SotColumnMuxArray"
tgate_column_mux_mod = "mram/tgate_column_mux_sotfet"
reference_column_mux_mod = "mram/sot_ref_tgate_column_mux"

sense_amp = "sot_sense_amp_array.sot_sense_amp"
sense_amp_ref = "mram/sot_sense_ref_mram"
sense_amp_mod = "mram/sot_sense_amp_mram"
sense_amp_array = "sot_sense_amp_array.SotSenseAmpArray"

bank_class = "sot_mram_bank.SotMramBank"
sram_class = "sotfet_mram.SotfetMram"
