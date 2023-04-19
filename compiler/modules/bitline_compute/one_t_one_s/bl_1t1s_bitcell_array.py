import debug
from modules.mram.sotfet.sotfet_mram_bitcell_array import sotfet_mram_bitcell_array


class Bl1t1sBitcellArray(sotfet_mram_bitcell_array):
    row_pins = ["wwl", "rwl"]
    col_pins = ["bl", "br", "blb", "brb"]

    def get_bitcell_connections(self, row, col):
        connections = []
        for pin in self.cell.pins:
            if pin in self.row_pins:
                pin = f"{pin}[{row}]"
            elif pin in self.col_pins:
                pin = f"{pin}[{col}]"
            connections.append(pin)
        return connections

    def add_pins(self):

        for col in range(self.column_size):
            for pin in self.col_pins:
                self.add_pin(f"{pin}[{col}]")
        for row in range(self.row_size):
            for pin in self.row_pins:
                self.add_pin(f"{pin}[{row}]")
        for pin in self.cell.pins:
            if pin not in self.row_pins + self.col_pins:
                self.add_pin(pin)

    def add_layout_pins(self):
        super().add_layout_pins()
        # bitlines
        col_pins = set(self.col_pins).difference(["bl", "br"])
        debug.info(2, "Bitcell col pins: %s", ' '.join(col_pins))
        for col_pin in col_pins:
            for col in range(self.column_size):
                self.copy_vertical_pin(col_pin, col, f"{col_pin}[{{}}]")
        # tap power
        for tap_inst in self.body_tap_insts:
            for pin_name in ["vdd", "gnd"]:
                if pin_name not in tap_inst.mod.pin_map:
                    continue
                pin = tap_inst.get_pin(pin_name)
                self.add_layout_pin(pin_name, pin.layer, pin.ll(), width=pin.width(),
                                    height=self.height - pin.by())


class SharedBBl1t1sBitcellArray(Bl1t1sBitcellArray):
    col_pins = ["bl", "br", "blb"]
