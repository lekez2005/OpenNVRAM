from importlib import reload

import debug
from base import design
from base import utils
from base.vector import vector
from globals import OPTS


class sense_amp_array(design.design):
    """
    Array of sense amplifiers to read the bitlines through the column mux.
    Dynamically generated sense amp array for all bitlines.
    """

    def __init__(self, word_size, words_per_row):
        design.design.__init__(self, "sense_amp_array")
        debug.info(1, "Creating {0}".format(self.name))

        c = reload(__import__(OPTS.sense_amp))
        self.mod_sense_amp = getattr(c, OPTS.sense_amp)
        self.amp = self.mod_sense_amp(OPTS.sense_amp_mod)
        self.add_mod(self.amp)

        self.word_size = word_size
        self.words_per_row = words_per_row
        self.row_size = self.word_size * self.words_per_row

        self.height = self.amp.height

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_pins(self):

        for i in range(0, self.row_size, self.words_per_row):
            index = int(i/self.words_per_row)
            self.add_pin("data[{0}]".format(index))
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))

        self.add_pin("en")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_layout(self):

        self.add_sense_amp()
        self.connect_rails()
        self.add_dummy_poly(self.amp, self.amp_insts, self.words_per_row, from_gds=True)
        self.fill_array_layer("nwell", self.amp, self.amp_insts)
        
        

    def add_sense_amp(self):
            
        bl_pin = self.amp.get_pin("bl")            
        br_pin = self.amp.get_pin("br")
        dout_pin = self.amp.get_pin("dout")

        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.row_size)


        self.amp_insts = []
        
        for i in range(0,self.row_size,self.words_per_row):

            name = "sa_d{0}".format(i)
            amp_position = vector(self.bitcell_offsets[i], 0)
            
            bl_offset = amp_position + bl_pin.ll().scale(1,0)
            br_offset = amp_position + br_pin.ll().scale(1,0)
            dout_offset = amp_position + dout_pin.ll()

            self.amp_insts.append(self.add_inst(name=name,
                          mod=self.amp,
                          offset=amp_position))
            index = int(i / self.words_per_row)

            self.connect_inst(["bl[{0}]".format(i),"br[{0}]".format(i), 
                               "data[{0}]".format(index),
                               "en", "vdd", "gnd"])

            self.add_layout_pin(text="bl[{0}]".format(i),
                                layer="metal2",
                                offset=bl_offset,
                                width=bl_pin.width(),
                                height=bl_pin.height())
            self.add_layout_pin(text="br[{0}]".format(i),
                                layer="metal2",
                                offset=br_offset,
                                width=br_pin.width(),
                                height=br_pin.height())
                           
            self.add_layout_pin(text="data[{0}]".format(index),
                                layer="metal3",
                                offset=dout_offset,
                                width=dout_pin.width(),
                                height=dout_pin.height())

        self.width = self.amp_insts[-1].rx()


    def connect_rails(self):
        # add vdd rail across entire array
        vdd_pin = self.amp.get_pin("vdd")
        vdd_offset = vdd_pin.ll().scale(0,1)
        self.add_layout_pin(text="vdd",
                      layer="metal1",
                      offset=vdd_offset,
                      width=self.width,
                      height=vdd_pin.height())

        # NOTE:the gnd rails are vertical so it is not connected horizontally
        # add gnd rail across entire array
        gnd_pins = self.amp.get_pins("gnd")
        for gnd_pin in gnd_pins:
            gnd_offset = gnd_pin.ll().scale(0,1)
            self.add_layout_pin(text="gnd",
                          layer="metal1",
                          offset=gnd_offset,
                          width=self.width,
                          height=gnd_pin.height())

        # add sclk rail across entire array
        en_pin = self.amp.get_pin("en")
        self.add_layout_pin(text="en",
                      layer="metal1",
                      offset=en_pin.ll().scale(0,1),
                      width=self.width,
                      height=en_pin.height())

    def analytical_delay(self, slew, load=0.0):
        return self.amp.analytical_delay(slew=slew, load=load)
        
