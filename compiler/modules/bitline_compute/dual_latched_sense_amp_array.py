from modules.sense_amp_array import sense_amp_array


class dual_latched_sense_amp_array(sense_amp_array):

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))

            self.add_pin("and[{0}]".format(i))
            self.add_pin("nor[{0}]".format(i))

        self.add_pin("en")
        self.add_pin("preb")
        self.add_pin("sampleb")
        self.add_pin("diff")
        self.add_pin("diffb")
        self.add_pin("vref")
        self.add_pin("vdd")
        self.add_pin("gnd")

    @property
    def bus_pins(self):
        return ["bl", "br", "and", "nor"]
