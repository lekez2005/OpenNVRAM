from modules.sense_amp_array import sense_amp_array


class sotfet_mram_sense_amp_array(sense_amp_array):

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))
            self.add_pin("data[{0}]".format(i))

        for pin_name in ["en", "preb", "sampleb", "br_reset", "vref", "vdd", "gnd"]:
            self.add_pin(pin_name)
