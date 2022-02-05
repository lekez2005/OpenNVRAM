from base.vector import vector
from modules.mram.sotfet.sotfet_mram_bitcell_array import sotfet_mram_bitcell_array


class sotfet_1t1s_bitcell_array(sotfet_mram_bitcell_array):
    def add_body_tap_power_pins(self):
        tap_offsets = self.bitcell_x_offsets[1]
        for pin in self.body_tap.get_pins("gnd"):
            for x_offset in tap_offsets:
                self.add_layout_pin("gnd", pin.layer,
                                    offset=vector(x_offset + pin.lx(), pin.by()),
                                    height=self.height - pin.by(), width=pin.width())
