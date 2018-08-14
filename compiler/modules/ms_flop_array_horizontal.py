from contact import m1m2
from tech import drc
from vector import vector
from ms_flop_array import ms_flop_array


class ms_flop_array_horizontal(ms_flop_array):
    def __init__(self, columns, word_size, name=""):
        if name=="":
            name = "flop_array_c{0}_w{1}_horiz".format(columns,word_size)
        ms_flop_array.__init__(self, columns, word_size, name)
        self.offset_all_coordinates()

    def add_in_out_pins(self):
        m1m2_layers = ("metal1", "via1", "metal2")
        m2m3_layers = ("metal2", "via2", "metal3")
        via_space = 2*self.m2_width
        rail_pitch = self.m2_width + drc["parallel_via_space"]

        self.m1_rail_height = self.wide_m1_space + self.word_size*rail_pitch
        self.min_y = -via_space - m1m2.second_layer_height - self.m1_rail_height
        self.max_y = self.ms_inst[0].get_pin("dout").uy() + via_space +\
                     m1m2.second_layer_height + self.m1_rail_height + self.m2_width
        for i in range(self.word_size):
            din_pins = self.ms_inst[i].get_pins("din")
            if len(din_pins) > 1:
                din_pin = filter(lambda x: x.layer == "metal2", din_pins)[0]
            else:
                din_pin = din_pins[0]

            via_offset = vector(din_pin.lx(), - via_space - m1m2.second_layer_height)
            self.add_rect("metal2", width=din_pin.width(), height=din_pin.by()-via_offset.y,
                          offset=via_offset)
            self.add_contact(layers=m1m2_layers, offset=via_offset)
            self.add_rect("metal1", height=self.m1_rail_height, width=din_pin.width(),
                          offset=vector(din_pin.lx(), via_offset.y-self.m1_rail_height))

            rail_y = self.min_y + i*rail_pitch
            self.add_contact(layers=m1m2_layers, offset=vector(din_pin.lx()+m1m2.second_layer_height,
                                                               rail_y), rotate=90)
            self.add_layout_pin(text="din[{}]".format(i),
                                layer="metal2",
                                offset=vector(0, rail_y),
                                width=self.width,
                                height=self.m2_width)

            self.add_contact(layers=m2m3_layers, offset=vector(din_pin.lx() + m1m2.second_layer_height,
                                                               rail_y), rotate=90)
            self.add_layout_pin(text="din[{}]".format(i),
                                layer="metal3",
                                offset=vector(0, rail_y),
                                width=self.width,
                                height=self.m2_width)


            dout_pin = self.ms_inst[i].get_pin("dout")

            via_offset = vector(dout_pin.lx(), dout_pin.uy() + via_space)
            self.add_rect("metal2", width=dout_pin.width(), height=via_offset.y - dout_pin.uy(),
                          offset=dout_pin.ul())
            self.add_contact(layers=m1m2_layers, offset=via_offset)
            self.add_rect("metal1", height=self.m1_rail_height+m1m2.second_layer_height, width=dout_pin.width(),
                          offset=vector(dout_pin.lx(), via_offset.y))

            rail_y = self.max_y - i * rail_pitch - self.m2_width
            self.add_contact(layers=m1m2_layers, offset=vector(dout_pin.lx() + m1m2.second_layer_height,
                                                               rail_y), rotate=90)

            self.add_layout_pin(text="dout[{}]".format(i),
                                layer="metal2",
                                offset=vector(0, rail_y),
                                width=self.width,
                                height=self.m2_width)




            doutbar_pin = self.ms_inst[i].get_pin("dout_bar")
            self.add_layout_pin(text="dout_bar[{}]".format(i),
                                layer="metal2",
                                offset=doutbar_pin.ll(),
                                width=doutbar_pin.width(),
                                height=doutbar_pin.height())

            self.height = self.max_y - self.min_y
