from base.vector import vector
from modules.sense_amp_array import sense_amp_array


class latched_sense_amp_array(sense_amp_array):

    def create_layout(self):
        self.add_sense_amp()
        self.add_layout_pins()
        self.fill_array_layer("nwell", self.amp)
        self.add_dummy_poly(self.amp, self.amp_insts, self.words_per_row,
                            from_gds=True)

    def add_pins(self):

        for i in range(0, self.row_size, self.words_per_row):
            index = int(i/self.words_per_row)
            self.add_pin("bl[{0}]".format(index))
            self.add_pin("br[{0}]".format(index))
            self.add_pin("data[{0}]".format(index))

        self.add_pin("en")
        self.add_pin("preb")
        self.add_pin("sampleb")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def get_connections(self, index):
        return ["bl[{0}]".format(index), "br[{0}]".format(index), "data[{0}]".format(index),
                "en", "preb", "sampleb", "vdd", "gnd"]

    def add_layout_pins(self):

        self.extend_vertical_pins("bl")
        self.extend_vertical_pins("br")
        self.extend_vertical_pins("dout", "data")

        self.extend_horizontal_pins("vdd")
        self.extend_horizontal_pins("gnd")
        self.extend_horizontal_pins("en")
        self.extend_horizontal_pins("preb")
        self.extend_horizontal_pins("sampleb")
