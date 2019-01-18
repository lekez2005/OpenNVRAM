from importlib import reload

import debug
from base import design
from base import utils
from base.vector import vector
from globals import OPTS
from tech import layer as tech_layers
from tech import purpose as tech_purpose


class tri_gate_array(design.design):
    """
    Dynamically generated tri gate array of all bitlines.  words_per_row
    """

    def __init__(self, columns, word_size):
        """Intial function of tri gate array """
        design.design.__init__(self, "tri_gate_array")
        debug.info(1, "Creating {0}".format(self.name))

        c = reload(__import__(OPTS.tri_gate))
        self.mod_tri_gate = getattr(c, OPTS.tri_gate)
        self.tri = self.mod_tri_gate("tri_gate")
        self.add_mod(self.tri)

        self.columns = columns
        self.word_size = word_size

        self.words_per_row = int(self.columns / self.word_size)
        self.height = self.tri.height
        
        self.create_layout()
        self.DRC_LVS()

    def create_layout(self):
        """generate layout """
        self.add_pins()
        self.create_array()
        self.add_layout_pins()
        self.connect_en_pins()
        self.fill_implants_and_nwell()

    def add_pins(self):
        """create the name of pins depend on the word size"""
        for i in range(self.word_size):
            self.add_pin("in[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("out[{0}]".format(i))
        for pin in ["en", "en_bar", "vdd", "gnd"]:
            self.add_pin(pin)

    def create_array(self):
        """add tri gate to the array """
        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.columns)
        self.tri_inst = {}
        for i in range(0,self.columns,self.words_per_row):
            name = "Xtri_gate{0}".format(i)
            base = vector(self.bitcell_offsets[i], 0)
            self.tri_inst[i]=self.add_inst(name=name,
                                           mod=self.tri,
                                           offset=base)
            index = int(i/self.words_per_row)
            self.connect_inst(["in[{0}]".format(index),
                               "out[{0}]".format(index),
                               "en", "en_bar", "vdd", "gnd"])
        self.width = self.tri_inst[i].rx()

    def connect_en_pins(self):
        previous_index = 0
        for i in range(1, self.columns):
            if i % self.words_per_row == 0:
                right_x_offset = self.bitcell_offsets[previous_index] + self.tri.width
                for pin_name in ["en", "en_bar"]:
                    prev_pin = self.tri_inst[previous_index].get_pin(pin_name)
                    current_pin = self.tri_inst[i].get_pin(pin_name)
                    width = max(current_pin.lx() - right_x_offset, self.m2_width) # prevent zero area rect when pins align
                    self.add_rect(current_pin.layer, offset=vector(right_x_offset, prev_pin.by()),
                                  width=width)
                previous_index = i

    def fill_implants_and_nwell(self):

        # fill nwell
        nwell_rects = self.tri.gds.getShapesInLayer(tech_layers["nwell"])
        self.fill_layer(nwell_rects[0], "nwell")
        # fill pimplant
        nimplants = self.tri.gds.getShapesInLayer(tech_layers["nimplant"])
        top_implant = max(nimplants, key=lambda x: x[1][1])
        self.fill_layer(top_implant, "nimplant")
        


    def fill_layer(self, rect, layer_name):
        # find last tri state
        last_key = list(range(0, self.columns, self.words_per_row))[-1]
        last_tri_state = self.tri_inst[last_key]

        (ll, ur) = rect
        x_extension = ur[0] - self.tri.width
        self.add_rect(layer_name, offset=ll, width=last_tri_state.rx() + x_extension, height=ur[1] - ll[1])


    def add_layout_pins(self):
        
        for i in range(0,self.columns,self.words_per_row):
            index = int(i/self.words_per_row)

            in_pin = self.tri_inst[i].get_pin("in")
            self.add_layout_pin(text="in[{0}]".format(index),
                                layer="metal2",
                                offset=in_pin.ll(),
                                width=in_pin.width(),
                                height=in_pin.height())

            out_pin = self.tri_inst[i].get_pin("out")
            self.add_layout_pin(text="out[{0}]".format(index),
                                layer="metal2",
                                offset=out_pin.ll(),
                                width=out_pin.width(),
                                height=out_pin.height())



        last_instance_key = max(map(int, self.tri_inst.keys()))
        width = self.tri_inst[last_instance_key].rx()
        en_pin = self.tri_inst[0].get_pin("en")
        self.add_layout_pin(text="en",
                            layer="metal2",
                            offset=en_pin.ll())
        
        enbar_pin = self.tri_inst[0].get_pin("en_bar")
        self.add_layout_pin(text="en_bar",
                            layer="metal2",
                            offset=enbar_pin.ll())
        
        vdd_pin = self.tri_inst[0].get_pin("vdd")
        self.add_layout_pin(text="vdd",
                            layer="metal1",
                            offset=vdd_pin.ll().scale(0, 1),
                            width=width,
                            height=vdd_pin.height())
            
        for gnd_pin in self.tri_inst[0].get_pins("gnd"):
            if gnd_pin.layer=="metal1":
                self.add_layout_pin(text="gnd",
                                    layer="metal1",
                                    offset=gnd_pin.ll().scale(0, 1),
                                    width=width,
                                    height=gnd_pin.height())


    def analytical_delay(self, slew, load=0.0):
        return self.tri.analytical_delay(slew = slew, load = load)
        
