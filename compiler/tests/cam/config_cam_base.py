import os

# modules
decoder_flops = True
bitcell = "cam_bitcell"
replica_bitcell = "cam_replica_bitcell"
bitcell_array = "cam_bitcell_array"
sense_amp_mod = "cam_sense_amp"
write_driver = "cam_write_driver"
write_driver_array = "cam_write_driver_array"
cam_sl_driver = "cam_sl_driver"
address_mux = "address_mux"
address_mux_array = "address_mux_array"
sl_driver_array = "sl_driver_array"
ml_precharge_array = "ml_precharge_array"
tag_flop_array = "tag_flop_array"
replica_bitline = "cam_replica_bitline"
col_decoder = "cam_column_decoder"
control_logic = "cam_control_logic"
body_tap = "cam_body_tap"
search_sense_amp_array = "search_sense_amp_array"
cam_block = "cam_block"
ml_precharge = "matchline_precharge"

wwl_buffer_stages = [4, 8, 16]
bank_gate_buffers = {  # buffers for bank gate. "default" used for unspecified signals
    "default": [2, 4, 8],
    "clk": [2, 6, 12, 24, 24],
    "w_en": [2, 8, 24],
    "search_en": [2, 8, 24]
}

# cam config
word_size = 32
num_words = 256
num_banks = 2
words_per_row = 1

# simulation
slew_rate = 0.005  # in nanoseconds
c_load = 1  # femto-farads
setup_time = 0.015  # in nanoseconds
feasible_period = 1.8  # in nanoseconds
duty_cycle = 0.35

spectre_format = "psfbin"

openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "openram_cam")
spice_file = os.path.join(openram_temp, 'temp.sp')
pex_spice = os.path.join(openram_temp, 'pex.sp')
reduced_spice = os.path.join(openram_temp, 'reduced.sp')
gds_file = os.path.join(openram_temp, 'temp.gds')








