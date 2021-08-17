from characterizer import SpiceCharacterizer
from shared_decoder.spice_dut import SpiceDut


class SimStepsGenerator(SpiceCharacterizer):
    def create_dut(self):
        stim = SpiceDut(self.sf, self.corner)
        stim.words_per_row = self.sram.words_per_row
        return stim
