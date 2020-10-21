from modules.sotfet.fast_ramp.sf_fast_ramp_cam_bank import SfFastRampCamBank
from modules.sotfet.sf_cam import SfCam


class SfFastRampCam(SfCam):
    """
    CMOS cam supporting write and search operations only
    Goal is to mirror the behavior of the SOTFET CAM
    Differs from SOTFET CAM in the bitline and search line logic
    """

    def create_bank_module(self):
        self.bank = SfFastRampCamBank(word_size=self.word_size, num_words=self.num_words_per_bank,
                                      words_per_row=self.words_per_row, name="bank")
        self.add_mod(self.bank)

    @staticmethod
    def add_wordline_connections():
        return []

    def add_wordline_pins(self):
        pass
