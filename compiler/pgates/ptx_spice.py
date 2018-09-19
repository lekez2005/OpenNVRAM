import debug
import design
import ptx
from tech import drc
from vector import vector


class ptx_spice(ptx.ptx):
    """
    Module for representing spice transistor. No layout is drawn but module can still be instantiated for use in LVS
    """

    def __init__(self, width=drc["minwidth_tx"], mults=1, tx_type="nmos", contact_pwell=True, contact_nwell=True):
        name = "{0}_m{1}_w{2}".format(tx_type, mults, width)
        if not contact_pwell:
            name += "_no_p"
        if not contact_nwell:
            name += "_no_n"
        design.design.__init__(self, name)
        debug.info(3, "create ptx_spice structure {0}".format(name))

        self.tx_type = tx_type
        self.mults = mults
        self.tx_width = width

        self.create_spice()
        self.create_layout()

    def create_layout(self):
        self.width = self.height = self.m1_width
        self.add_rect("boundary", offset=vector(0, 0), width=self.width, height=self.height)

