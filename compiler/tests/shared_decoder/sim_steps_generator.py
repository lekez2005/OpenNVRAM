from characterizer import SpiceCharacterizer
from globals import OPTS
from shared_decoder.shared_probe import SharedProbe
from shared_decoder.spice_dut import SpiceDut


class SimStepsGenerator(SpiceCharacterizer):
    def create_dut(self):
        stim = SpiceDut(self.sf, self.corner)
        stim.words_per_row = self.sram.words_per_row
        return stim

    def create_probe(self):
        self.probe = SharedProbe(self.sram, OPTS.pex_spice)
