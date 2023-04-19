from modules.bitcell_aligned_array import BitcellAlignedArray
from modules.bitline_compute.dual_latched_sense_amp_array import dual_latched_sense_amp_array


class bl_1t1s_sense_amp_array(dual_latched_sense_amp_array):

    def add_pins(self):
        BitcellAlignedArray.add_pins(self)

    @property
    def bus_pins(self):
        return ["bl", "br", "blb", "brb", "and", "nor"]
