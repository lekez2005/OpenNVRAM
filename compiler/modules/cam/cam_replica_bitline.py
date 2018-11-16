import itertools
from modules import replica_bitline
from vector import vector


class cam_replica_bitline(replica_bitline.replica_bitline):
    def connect_inst(self, args, check=True):
        module = self.insts[-1].mod
        if module.name == "cam_replica_cell_6t":
            args = ["bl[0]", "br[0]", "gnd", "gnd", "delayed_en", "rbc_ml", "vdd", "gnd"]
        elif module.name == "bitline_load":
            ml_nets = ["ml[{}]".format(i) for i in range(self.bitcell_loads)]
            wl_nets = ["gnd"]*self.bitcell_loads
            mixed = list(itertools.chain.from_iterable(zip(wl_nets, ml_nets)))

            args = ["bl[0]", "br[0]"] + ["gnd", "gnd"] + mixed + ["vdd", "gnd"]
        super(cam_replica_bitline, self).connect_inst(args, self)

    def route(self):
        super(cam_replica_bitline, self).route()
        self.connect_searchlines_to_gnd()

    def connect_searchlines_to_gnd(self):
        """Connect search line to gnd, assumes M1 to M4 pin exists below sl and slb pin"""
        sl_pin = self.rbc_inst.get_pin("SL")
        gnd_pin = self.get_pin("gnd")
        self.add_rect("metal1", offset=vector(gnd_pin.rx(), sl_pin.by()), width=sl_pin.rx() - gnd_pin.rx())

