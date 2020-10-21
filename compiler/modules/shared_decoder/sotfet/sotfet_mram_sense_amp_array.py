from modules.sense_amp_array import sense_amp_array


class sotfet_mram_sense_amp_array(sense_amp_array):
    def create_layout(self):
        self.add_sense_amp()
        self.add_layout_pins()
        self.fill_array_layer("nwell", self.amp)
        self.add_dummy_poly(self.amp, self.amp_insts, self.words_per_row,
                            from_gds=True)

    def add_pins(self):
        for i in range(0, self.row_size, self.words_per_row):
            index = int(i / self.words_per_row)
            self.add_pin("bl[{0}]".format(index))
            self.add_pin("br[{0}]".format(index))
            self.add_pin("data[{0}]".format(index))

        for pin_name in ["en", "preb", "sampleb", "br_reset", "vref", "vdd", "gnd"]:
            self.add_pin(pin_name)

    def get_connections(self, index):
        return ["bl[{0}]".format(index), "br[{0}]".format(index), "br_reset",
                "data[{0}]".format(index), "en", "gnd", "preb", "sampleb",
                "vdd", "vref"]

    def add_layout_pins(self):
        self.extend_vertical_pins("bl")
        self.extend_vertical_pins("br")
        self.extend_vertical_pins("dout", "data")

        for pin_name in ["vdd", "gnd", "en", "preb", "sampleb", "br_reset", "vref"]:
            self.extend_horizontal_pins(pin_name)
