from modules.precharge_array import precharge_array


class BitlineDischargeArray(precharge_array):
    def get_connections(self, col):
        return f"bl[{col}] br[{col}] bl_discharge, br_discharge gnd".split()

    def create_layout(self):
        self.add_insts()
        for pin_name in ["gnd", "bl_discharge", "br_discharge"]:

            for pin in self.child_insts[0].get_pins(pin_name):
                self.add_layout_pin(pin_name, pin.layer, pin.ll(), height=pin.height(),
                                    width=self.width - pin.lx())
