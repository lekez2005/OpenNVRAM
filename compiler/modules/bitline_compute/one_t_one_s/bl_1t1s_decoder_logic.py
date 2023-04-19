import debug
from modules.bitline_compute.decoder_logic import DecoderLogic
from pgates.pinv import pinv
from pgates.pnand2 import pnand2


class DecLogicNand(pnand2):
    @classmethod
    def get_name(cls, *args, **kwargs):
        return "decoder_logic_nand"


class DecLogicInverter(pinv):
    @classmethod
    def get_name(cls, *args, **kwargs):
        return "decoder_logic_inv"


class Bl1t1sDecoderLogic(DecoderLogic):
    def create_modules(self):
        self.create_bitcell()
        kwargs = dict(size=1, align_bitcell=True, same_line_inputs=True,
                      contact_nwell=False, contact_pwell=False,
                      height=self.bitcell.height)

        self.nand = DecLogicNand(**kwargs)
        self.add_mod(self.nand)
        self.inv = DecLogicInverter(**kwargs)
        self.add_mod(self.inv)

        debug.info(2, "Decoder logic height = %.2g", self.nand.height)
