import math
import os

from base.contact import m3m4

default_base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "../../../.."))
base_dir = os.environ.get("CARAVEL_WORKSPACE", default_base_dir)
gds_dir = os.path.join(base_dir, "gds")
xschem_dir = os.path.join(base_dir, "xschem")
verilog_dir = os.path.join(base_dir, "verilog", "rtl")
spice_dir = os.path.join(base_dir, "netgen")

esd_diode_length = 15
esd_diode_width = 1.5
esd_diode_mults = 10
esd_num_contacts = 5
esd_pad_to_diode = 10

res_short_pin_shift = 0.5

module_x_space = 5
module_y_space = 5

rail_width = m3m4.w_1
rail_space = 0.35
rail_pitch = rail_width + rail_space

mid_control_pins = ["clk", "sense_trig", "web"]


class SramConfig:
    sram = None
    WL_3_3V = "_wl_3v"
    WL_1_8V = ""

    def __init__(self, word_size, num_rows, words_per_row, num_banks=1,
                 voltage_mode=WL_1_8V):
        self.word_size = word_size
        self.num_rows = num_rows
        self.num_banks = num_banks
        self.words_per_row = words_per_row
        self.voltage_mode = voltage_mode

        self.num_words = num_banks * words_per_row * num_rows
        self.address_width = int(math.log2(self.num_words))

        banks_str = f"_bank_{num_banks}" * (num_banks > 1)
        words_per_row_str = f"_wpr_{words_per_row}" * (words_per_row > 1)

        self.module_name = f"r_{self.num_rows}_w_{word_size}{words_per_row_str}" \
                           f"{banks_str}{voltage_mode}"

    @property
    def gds_file(self):
        return os.path.join(gds_dir, f"{self.module_name}.gds")

    def get_gds_file(self):
        return self.gds_file

    @property
    def spice_file(self):
        return os.path.join(base_dir, "netgen", f"{self.module_name}.spice")

    @property
    def lvs_spice_file(self):
        return os.path.join(base_dir, "netgen", f"{self.module_name}.lvs.spice")


sram_configs = [
    # SramConfig(word_size=64, num_rows=64, words_per_row=1),
    SramConfig(word_size=32, num_rows=32, words_per_row=1),
    # SramConfig(word_size=64, num_rows=256, words_per_row=4),
    SramConfig(word_size=64, num_rows=64, words_per_row=2),
    SramConfig(word_size=32, num_rows=32, words_per_row=1, voltage_mode=SramConfig.WL_3_3V),
    SramConfig(word_size=16, num_rows=16, words_per_row=1)
]

# simulation config
simulation_sel_index = 0
simulation_other_mask = 1
simulation_other_data = 0
simulation_esd_voltage = 3.3

# const_config = sram_configs[1]
# # const_config = SramConfig(word_size=16, num_rows=16, words_per_row=8)
# sram_configs = [SramConfig(word_size=const_config.word_size, num_rows=const_config.num_rows,
#                            words_per_row=const_config.words_per_row) for i in range(4)]
# sram_configs = [
#     SramConfig(word_size=8, num_rows=32, words_per_row=1),
#     SramConfig(word_size=8, num_rows=32, words_per_row=1),
#     SramConfig(word_size=8, num_rows=32, words_per_row=1),
#     SramConfig(word_size=8, num_rows=32, words_per_row=1)
# ]
