from importlib import reload

import debug
from base import design
from base import utils
from base.library_import import library_import
from base.vector import vector
from globals import OPTS


@library_import
class ms_flop_tap(design.design):
    """
    Nwell and Psub body taps for ms flop
    """
    pin_names = []
    lib_name = 'ms_flop_tap'


class ms_flop_array(design.design):
    """
    An Array of D-Flipflops used for to store Data_in & Data_out of
    Write_driver & Sense_amp, address inputs of column_mux &
    hierdecoder
    """
    body_tap_insts = []

    def __init__(self, columns, word_size, name="", align_bitcell=False, flop_mod=None,
                 flop_tap_name=None):
        self.columns = columns
        self.word_size = word_size
        if flop_mod is None:
            flop_mod = OPTS.ms_flop
        if name == "":
            name = "flop_array_c{0}_w{1}".format(columns, word_size)
            name += "_{}".format(flop_mod) if not flop_mod == OPTS.ms_flop else ""
        design.design.__init__(self, name)
        debug.info(1, "Creating {}".format(self.name))

        c = reload(__import__(OPTS.ms_flop))
        self.mod_ms_flop = getattr(c, OPTS.ms_flop)
        self.ms = self.mod_ms_flop(flop_mod)
        self.add_mod(self.ms)

        self.body_tap = ms_flop_tap(flop_tap_name)
        self.add_mod(self.body_tap)

        self.height = self.ms.height
        self.words_per_row = int(self.columns / self.word_size)
        self.align_bitcell = align_bitcell

        self.create_layout()

    def create_layout(self):
        self.add_pins()
        self.create_ms_flop_array()
        self.add_dummy_poly(self.ms, self.ms_inst.values(), self.words_per_row, from_gds=True)
        self.fill_array_layer("nwell", self.ms)
        self.add_layout_pins()
        self.DRC_LVS()

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("din[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("dout[{0}]".format(i))
            self.add_pin("dout_bar[{0}]".format(i))
        self.add_pin("clk")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_ms_flop_array(self):
        if self.align_bitcell:
            (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.columns)
        else:
            self.bitcell_offsets = [i * self.ms.width for i in range(self.columns)]
            self.tap_offsets = []
        self.ms_inst={}
        for i in range(0,self.columns,self.words_per_row):
            name = "dff{0}".format(i)
            base = vector(self.bitcell_offsets[i], 0)
            mirror = "R0"
            index = int(i / self.words_per_row)
            self.ms_inst[index]=self.add_inst(name=name,
                                                             mod=self.ms,
                                                             offset=base,
                                                             mirror=mirror)
            self.connect_inst(["din[{0}]".format(index),
                               "dout[{0}]".format(index),
                               "dout_bar[{0}]".format(index),
                               "clk",
                               "vdd", "gnd"])

        for x_offset in self.tap_offsets:
            self.body_tap_insts.append(self.add_inst(name=self.body_tap.name, mod=self.body_tap,
                                                     offset=vector(x_offset, 0)))
            self.connect_inst([])

        self.width = self.ms_inst[index].rx()

    def add_layout_pins(self):

        self.add_in_out_pins()
        
        for i in range(self.word_size):

            for gnd_pin in self.ms_inst[i].get_pins("gnd"):
                if gnd_pin.layer!="metal2":
                    continue
                self.add_layout_pin(text="gnd",
                                    layer="metal2",
                                    offset=gnd_pin.ll(),
                                    width=gnd_pin.width(),
                                    height=gnd_pin.height())
            
            
        # Continous clk rail along with label.
        self.add_layout_pin(text="clk",
                            layer="metal1",
                            offset=self.ms_inst[0].get_pin("clk").ll().scale(0,1),
                            width=self.width,
                            height=self.ms_inst[0].get_pin("clk").height())

        
        # Continous vdd rail along with label.
        for vdd_pin in self.ms_inst[i].get_pins("vdd"):
            if vdd_pin.layer!="metal1":
                continue
            self.add_layout_pin(text="vdd",
                                layer="metal1",
                                offset=vdd_pin.ll().scale(0,1),
                                width=self.width,
                                height=vdd_pin.height())

        # Continous gnd rail along with label.
        for gnd_pin in self.ms_inst[i].get_pins("gnd"):
            if gnd_pin.layer!="metal1":
                continue
            self.add_layout_pin(text="gnd",
                                layer="metal1",
                                offset=gnd_pin.ll().scale(0,1),
                                width=self.width,
                                height=gnd_pin.height())
    def add_in_out_pins(self):
        for i in range(self.word_size):
            din_pins = self.ms_inst[i].get_pins("din")
            for din_pin in din_pins:
                self.add_layout_pin(text="din[{}]".format(i),
                                    layer=din_pin.layer,
                                    offset=din_pin.ll(),
                                    width=din_pin.width(),
                                    height=din_pin.height())

            dout_pin = self.ms_inst[i].get_pin("dout")
            self.add_layout_pin(text="dout[{}]".format(i),
                                layer="metal2",
                                offset=dout_pin.ll(),
                                width=dout_pin.width(),
                                height=dout_pin.height())

            doutbar_pin = self.ms_inst[i].get_pin("dout_bar")
            self.add_layout_pin(text="dout_bar[{}]".format(i),
                                layer="metal2",
                                offset=doutbar_pin.ll(),
                                width=doutbar_pin.width(),
                                height=doutbar_pin.height())

    def analytical_delay(self, slew, load=0.0):
        return self.ms.analytical_delay(slew=slew, load=load)

