from modules.sense_amp_array import sense_amp_array


class dual_sense_amp_array(sense_amp_array):
    """
    Array of sense amplifiers to read the bitlines.
    Dynamically generated sense amp array for all bitlines.
    """

    @property
    def bus_pins(self):
        return ["bl", "br", "and", "nor"]

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))

            self.add_pin("and[{0}]".format(i))
            self.add_pin("nor[{0}]".format(i))

        self.add_pin("en")
        self.add_pin("en_bar")
        self.add_pin("search_ref")
        self.add_pin("vdd")
        self.add_pin("gnd")
