import itertools
from modules import replica_bitline
from vector import vector


class cam_replica_bitline_12t(replica_bitline.replica_bitline):
    def connect_inst(self, args, check=True):
        module = self.insts[-1].mod
        if module.name == "cam_replica_cell_12t":
            args = ["bl[0]", "br[0]", "gnd", "gnd", "delayed_en", "gnd", "rbc_ml", "vdd", "gnd"]
        elif module.name == "bitline_load":
            ml_nets = ["ml[{}]".format(i) for i in range(self.bitcell_loads)]
            wwl_nets = ["gnd"]*self.bitcell_loads
            wl_nets = ["gnd"]*self.bitcell_loads
            mixed = list(itertools.chain.from_iterable(zip(wl_nets, wwl_nets, ml_nets)))

            args = ["bl[0]", "br[0]"] + ["gnd", "gnd"] + mixed + ["vdd", "gnd"]
        super(cam_replica_bitline_12t, self).connect_inst(args, self)

    def route(self):
        super(cam_replica_bitline_12t, self).route()
        self.connect_searchlines_to_gnd()
        self.connect_write_wordlines_to_gnd()

    def connect_searchlines_to_gnd(self):
        """Connect search line to gnd, assumes M1 to M4 pin exists below sl and slb pin"""
        sl_pin = self.rbc_inst.get_pin("SL")
        gnd_pin = self.get_pin("gnd")
        self.add_rect("metal1", offset=vector(gnd_pin.rx(), sl_pin.by()), width=sl_pin.rx() - gnd_pin.rx())


    def connect_write_wordlines_to_gnd(self):
        """Connect write wordline wwl to gnd"""
        for row in range(self.bitcell_loads):
            wwl = "wwl[{}]".format(row)
            pin = self.rbl_inst.get_pin(wwl)
            start = vector(self.gnd_offset.x, pin.by())
            self.add_rect(layer="metal1",
                          offset=start,
                          width=pin.lx() - self.gnd_offset.x,
                          height=pin.height())

        wwl_pin = self.rbc_inst.get_pin("WWL")
        gnd_pin = self.get_pin("gnd")
        self.add_rect("metal1", offset=vector(gnd_pin.rx(), wwl_pin.by()), width=wwl_pin.lx() - gnd_pin.rx())


