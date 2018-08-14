import debug
import design
from tech import drc
from pinv import pinv
import contact
from bitcell_array import bitcell_array
from ptx import ptx
import utils
from vector import vector
from globals import OPTS

class replica_bitline(design.design):
    """
    Generate a module that simulates the delay of control logic 
    and bit line charging. Stages is the depth of the delay
    line and rows is the height of the replica bit loads.
    """

    def __init__(self, delay_stages, delay_fanout, bitcell_loads, name="replica_bitline"):
        design.design.__init__(self, name)

        g = reload(__import__(OPTS.delay_chain))
        self.mod_delay_chain = getattr(g, OPTS.delay_chain)

        g = reload(__import__(OPTS.replica_bitcell))
        self.mod_replica_bitcell = getattr(g, OPTS.replica_bitcell)

        c = reload(__import__(OPTS.bitcell))
        self.mod_bitcell = getattr(c, OPTS.bitcell)

        for pin in ["en", "out", "vdd", "gnd"]:
            self.add_pin(pin)
        self.bitcell_loads = bitcell_loads
        self.delay_stages = delay_stages
        self.delay_fanout = delay_fanout

        self.rail_offset = 0.5*drc["implant_to_implant"]

        self.create_modules()
        self.calculate_module_offsets()
        self.add_modules()
        self.route()
        self.calculate_dimensions()
        self.add_lvs_correspondence_points()

        self.DRC_LVS()

    def calculate_dimensions(self):
        top_gnd = sorted(self.dc_inst.get_pins("gnd"), key=lambda x: x.uy())[-1]
        self.height = max(top_gnd.uy(), self.rbl_inst.uy())
        self.width = self.right_vdd.rx()

    def calculate_module_offsets(self):
        """ Calculate all the module offsets """
        
        # These aren't for instantiating, but we use them to get the dimensions
        self.poly_contact_offset = vector(0.5*contact.poly.width,0.5*contact.poly.height)

        # M1/M2 routing pitch is based on contacted pitch
        self.m1_pitch = max(contact.m1m2.width,contact.m1m2.height) + max(self.m1_space,self.m2_space)
        self.m2_pitch = max(contact.m2m3.width,contact.m2m3.height) + max(self.m2_space,self.m3_space)
        
        # This corrects the offset pitch difference between M2 and M1
        self.offset_fix = vector(0.5*(self.m2_width-self.m1_width),0)

        # leave space below the cells for pins and bitcell overshoots
        self.bottom_y_offset = 3*self.m1_pitch

        self.left_vdd_offset = vector(0, 0)
        inverter_delay_chain_space = self.rail_height + drc["same_nwell_to_nwell"]

        self.delay_chain_offset = vector(self.rail_height + self.wide_m1_space,
                                         self.inv.height + self.bottom_y_offset + inverter_delay_chain_space)
        tx_y_offset = self.inv.height - (self.access_tx.implant_rect.offset.y + self.access_tx.implant_rect.height) \
                      - self.rail_offset + self.bottom_y_offset
        tx_x_offset = self.delay_chain_offset.x + 0.5*(self.access_tx.width - self.access_tx.active_width)
        self.access_tx_offset = vector(tx_x_offset, tx_y_offset)
        self.rbl_inv_offset = vector(self.access_tx_offset.x + self.access_tx.width +
                                     self.access_tx.poly_pitch-self.access_tx.poly_width, self.bottom_y_offset)

        gnd_space = 2*self.m1_space
        self.gnd_offset = vector(gnd_space + max(self.rbl_inv_offset.x + self.inv.width,
                                                 self.delay_chain_offset.x + self.delay_chain.width), 0)
        self.wl_x_offset = self.gnd_offset.x + self.rail_height + gnd_space
        bitcell_x_offset = self.wl_x_offset + self.m1_width + self.wide_m1_space - self.bitcell.get_pin("vdd").lx()

        self.bitcell_offset = vector(bitcell_x_offset, self.replica_bitcell.height + self.bottom_y_offset)
        self.rbl_offset = self.bitcell_offset



    def create_modules(self):
        """ Create modules for later instantiation """
        self.bitcell = self.replica_bitcell = self.mod_replica_bitcell()
        self.add_mod(self.bitcell)

        # This is the replica bitline load column that is the height of our array
        self.rbl = bitcell_array(name="bitline_load", cols=1, rows=self.bitcell_loads)
        self.add_mod(self.rbl)

        # FIXME: The FO and depth of this should be tuned
        self.delay_chain = self.mod_delay_chain([self.delay_fanout]*self.delay_stages, cells_per_row=2)
        self.add_mod(self.delay_chain)

        self.inv = pinv(rail_offset=self.rail_offset)
        self.add_mod(self.inv)

        self.access_tx = ptx(tx_type="pmos")
        self.add_mod(self.access_tx)

    def add_modules(self):
        """ Add all of the module instances in the logical netlist """
        # This is the threshold detect inverter on the output of the RBL
        self.rbl_inv_inst=self.add_inst(name="rbl_inv",
                                        mod=self.inv,
                                        offset=self.rbl_inv_offset,
                                        rotate=0)
        self.connect_inst(["bl[0]", "out", "vdd", "gnd"])

        self.tx_inst=self.add_inst(name="rbl_access_tx",
                                   mod=self.access_tx,
                                   offset=self.access_tx_offset,
                                   rotate=0)
        # D, G, S, B
        self.connect_inst(["vdd", "delayed_en", "bl[0]", "vdd"])
        # add the well and poly contact

        self.dc_inst=self.add_inst(name="delay_chain",
                                   mod=self.delay_chain,
                                   offset=self.delay_chain_offset,
                                   rotate=0)
        self.connect_inst(["en", "delayed_en", "vdd", "gnd"])

        self.rbc_inst=self.add_inst(name="bitcell",
                                    mod=self.replica_bitcell,
                                    offset=self.bitcell_offset,
                                    mirror="MX")
        self.connect_inst(["bl[0]", "br[0]", "delayed_en", "vdd", "gnd"])

        self.rbl_inst=self.add_inst(name="load",
                                    mod=self.rbl,
                                    offset=self.rbl_offset)
        self.connect_inst(["bl[0]", "br[0]"] + ["gnd"]*self.bitcell_loads + ["vdd", "gnd"])
        



    def route(self):
        """ Connect all the signals together """
        self.route_gnd()
        self.route_vdd()
        self.route_access_tx()
        self.route_enable()


    def route_access_tx(self):

        m1m2_layers = ("metal1", "via1", "metal2")

        # check if delay chain output is to the right or left
        output_inv = self.dc_inst.mod.output_inv
        z_pin = output_inv.get_pin("Z")
        a_pin = output_inv.get_pin("A")
        self.add_contact_center(layers=m1m2_layers, offset=z_pin.center() + self.delay_chain_offset)


        inverter_vdd = self.rbl_inv_inst.get_pin("vdd")
        if a_pin.lx() < z_pin.lx():
            mid1x = self.delay_chain_offset.x + self.dc_inst.mod.width
            mid2x = self.delay_chain_offset.x
        else:
            mid1x = self.delay_chain_offset.x
            mid2x = self.delay_chain_offset.x + self.dc_inst.mod.width

        z_y = z_pin.uy() + self.delay_chain_offset.y - 0.5*self.m2_width
        path_list = [vector(self.delay_chain_offset.x+z_pin.cx(), z_y),
                     vector(mid1x, z_y),
                     vector(mid1x, inverter_vdd.cy()),
                     vector(mid2x, inverter_vdd.cy())]
        self.add_path("metal2", path_list)

        # connect tx gate to delayed enable
        tx_gate_pin = self.tx_inst.get_pin("G")
        self.add_contact_center(layers=m1m2_layers, offset=tx_gate_pin.center())
        self.add_path("metal2", [tx_gate_pin.center(), vector(tx_gate_pin.cx(), inverter_vdd.cy())])

        # connect replica bitcell wl to delayed enable
        wl_pin = self.rbc_inst.get_pin("WL")
        self.add_path("metal2", [vector(self.delay_chain_offset.x + self.dc_inst.mod.width, inverter_vdd.cy()),
                                 vector(self.wl_x_offset+0.5*self.m2_width, inverter_vdd.cy()),
                                 vector(self.wl_x_offset+0.5*self.m2_width, wl_pin.by())])
        contact_offset = vector(self.wl_x_offset, wl_pin.by())
        self.add_contact(layers=m1m2_layers, offset=contact_offset)
        self.add_rect("metal1", offset=contact_offset, height=contact.m1m2.first_layer_height, width=wl_pin.lx()-self.wl_x_offset)

        # connect source to vdd
        source_pin = self.tx_inst.get_pin("S")
        self.add_path("metal1", [source_pin.center(), vector(source_pin.cx(), inverter_vdd.cy())])

        # connect drain to inverter input
        drain_pin = self.tx_inst.get_pin("D")
        inv_input_pin = self.rbl_inv_inst.get_pin("A")
        mid1x = drain_pin.cx() + self.m1_space
        self.add_path("metal1", [drain_pin.center(),
                                 vector(mid1x, drain_pin.cy()),
                                 vector(mid1x, inv_input_pin.cy()), inv_input_pin.center()])

        # connect drain to bitcell wordline
        bl_pin = self.rbc_inst.get_pin("BL")
        next_y = bl_pin.by() - 2*self.m2_space
        self.add_path("metal2", [vector(bl_pin.cx(), bl_pin.by()), vector(bl_pin.cx(), next_y),
                                 vector(mid1x-0.5*self.m1_width, next_y)])
        self.add_contact(layers=m1m2_layers, offset=vector(mid1x-0.5*self.m1_width, next_y))
        self.add_path("metal1", [vector(mid1x, next_y),
                                 vector(mid1x, inv_input_pin.cy())])

        # connect inverter output to out
        z_pin = self.rbl_inv_inst.get_pin("Z")
        contact1_offset = vector(z_pin.rx()-0.5*contact.m1m2.first_layer_height, z_pin.cy())

        self.add_contact_center(layers=m1m2_layers, offset=contact1_offset, rotate=90)
        self.add_path("metal2", [contact1_offset, vector(self.wl_x_offset, contact1_offset.y)])
        contact2_offset = vector(self.wl_x_offset+0.5*self.m1_width, contact1_offset.y)
        self.add_contact_center(layers=m1m2_layers, offset=contact2_offset, rotate=0)

        self.add_layout_pin(text="out",
                            layer="metal1",
                            offset=vector(self.wl_x_offset, 0),
                            width=self.m1_width,
                            height=contact2_offset.y)

        # metal 1 fill for gate contact
        fill_width = tx_gate_pin.width()
        fill_height = utils.ceil(drc["minarea_metal1_contact"] / fill_width)
        self.add_rect("metal1", width=fill_width, height=fill_height,
                      offset=vector(tx_gate_pin.lx(), tx_gate_pin.uy()-fill_height))

        # extend pwell from inverter to tx
        inv_nwell_y = self.inv.nwell_position.y + self.rbl_inv_offset.y
        nwell_width = self.rbl_inv_inst.rx()
        nwell_height = self.inv.nwell_rect.height
        self.add_rect(layer="nwell", width=nwell_width, height=nwell_height, offset=vector(0, inv_nwell_y))
        
    def route_vdd(self):
        # Add two vertical rails, one to the left of the delay chain and one to the right of the replica cells

        right_vdd_start = vector(self.bitcell_offset.x + self.bitcell.width + self.m1_pitch, 0)
        # It is the height of the entire RBL and bitcell
        self.right_vdd = self.add_layout_pin(text="vdd",
                            layer="metal1",
                            offset=right_vdd_start,
                            width=self.rail_height,
                            height=self.rbl.height+self.rbl_offset.y)

        # Connect the vdd pins of the bitcell load directly to vdd
        vdd_pins = self.rbl_inst.get_pins("vdd")
        for pin in vdd_pins:
            self.add_rect(layer="metal1",
                          offset=pin.lr(),
                          width=right_vdd_start.x-pin.rx(),
                          height=self.rail_height)

        # Also connect the replica bitcell vdd pin to vdd
        pin = self.rbc_inst.get_pin("vdd")
        offset = vector(right_vdd_start.x,pin.by())
        self.add_rect(layer="metal1",
                      offset=offset,
                      width=self.bitcell_offset.x-right_vdd_start.x,
                      height=self.rail_height)

        # Add a second vdd pin. No need for full length. It is must connect at the next level.
        self.add_layout_pin(text="vdd",
                            layer="metal1",
                            offset=self.left_vdd_offset,
                            width=self.rail_height,
                            height=self.dc_inst.uy())

        # Connect the vdd pins of the delay chain
        vdd_pins = self.dc_inst.get_pins("vdd")
        for pin in vdd_pins:
            offset = vector(self.left_vdd_offset.x, pin.by())
            self.add_rect(layer="metal1",
                          offset=offset,
                          width=pin.lx() - self.left_vdd_offset.x,
                          height=self.rail_height)
        inv_pin = self.rbl_inv_inst.get_pin("vdd")
        self.add_rect(layer="metal1",
                      offset=vector(self.left_vdd_offset.x, inv_pin.by()),
                      width=inv_pin.lx() - self.left_vdd_offset.x,
                      height=self.rail_height)

        
        
        
    def route_gnd(self):
        """ Route all signals connected to gnd """

        # It is the height of the entire RBL and bitcell
        self.add_layout_pin(text="gnd",
                            layer="metal1",
                            offset=self.gnd_offset,
                            width=self.rail_height,
                            height=max(self.dc_inst.uy(), self.rbl_inst.uy()))

        # connect bitcell wordlines to gnd
        for row in range(self.bitcell_loads):
            wl = "wl[{}]".format(row)
            pin = self.rbl_inst.get_pin(wl)
            start = vector(self.gnd_offset.x,pin.cy())
            self.add_rect(layer="metal1",
                          offset=start,
                          width=pin.lx() - self.gnd_offset.x,
                          height=self.m1_width)

        # connect replica bit load grounds
        rbl_gnds = self.rbl_inst.get_pins("gnd")
        for pin in rbl_gnds:
            if pin.layer == "metal1":
                self.add_rect(layer="metal1",
                              offset=vector(self.gnd_offset.x, pin.by()),
                              width=pin.lx() - self.gnd_offset.x,
                              height=self.rail_height)

        # connect replica bit cell to ground
        rbc_gnds = self.rbc_inst.get_pins("gnd")
        for pin in rbc_gnds:
            if pin.layer == "metal1":
                self.add_rect(layer="metal1",
                              offset=vector(self.gnd_offset.x, pin.by()),
                              width=pin.lx() - self.gnd_offset.x,
                              height=self.rail_height)

        # Connect the gnd pins of the delay chain
        vdd_pins = self.dc_inst.get_pins("gnd")
        for pin in vdd_pins:
            offset = pin.lr()
            self.add_rect(layer="metal1",
                          offset=offset,
                          width=self.gnd_offset.x-offset.x,
                          height=self.rail_height)
        inv_pin = self.rbl_inv_inst.get_pin("gnd")
        self.add_rect(layer="metal1",
                      offset=inv_pin.lr(),
                      width=self.gnd_offset.x-inv_pin.rx(),
                      height=self.rail_height)

    def route_enable(self):
        in_pin = self.dc_inst.get_pin("in")
        m1m2_layers = ("metal1", "via1", "metal2")
        self.add_contact_center(layers=m1m2_layers, offset=in_pin.center())
        mid1_x = self.left_vdd_offset.x + 0.5*self.rail_height
        mid2_x = self.left_vdd_offset.x + self.rail_height + 2*self.wide_m1_space
        # output pin should fullfill drc requirements
        fill_width = self.m1_width
        fill_height = utils.ceil(drc["minarea_metal1_contact"] / fill_width)

        self.add_path("metal2", [in_pin.center(), vector(mid1_x, in_pin.cy()), vector(mid1_x, fill_height),
                                 vector(mid2_x+contact.m1m2.second_layer_width, fill_height)])
        self.add_contact(layers=m1m2_layers, offset=vector(mid2_x, fill_height-contact.m1m2.first_layer_height))

        self.add_layout_pin(text="en",
                            layer="metal1",
                            offset=vector(mid2_x, 0),
                            width=self.m1_width,
                            height=fill_height)

        
    def add_lvs_correspondence_points(self):
        """ This adds some points for easier debugging if LVS goes wrong. 
        These should probably be turned off by default though, since extraction
        will show these as ports in the extracted netlist.
        """

        pin = self.rbl_inv_inst.get_pin("A")
        self.add_label_pin(text="bl[0]",
                           layer=pin.layer,
                           offset=pin.ll(),
                           height=pin.height(),
                           width=pin.width())

        pin = self.dc_inst.get_pin("out")
        self.add_label_pin(text="delayed_en",
                           layer=pin.layer,
                           offset=pin.ll(),
                           height=pin.height(),
                           width=pin.width())

