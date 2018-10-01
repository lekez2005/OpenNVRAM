from contact import m1m2
import contact
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
        m1m2_layers = contact.contact.m1m2_layers
        via_space = self.m1_space
        rail_pitch = self.m2_width + drc["parallel_via_space"]

        self.m1_rail_height = 0.5*m1m2.first_layer_width + self.m1_space + self.word_size*rail_pitch - self.m2_space
        self.min_y = -via_space - 0.5*m1m2.second_layer_width - self.m1_rail_height

        gnd_pins = self.ms_inst[0].get_pins("gnd")
        top_gnd_pin = max(gnd_pins, key=lambda x: x.uy())

        self.max_y = top_gnd_pin.uy() + self.m1_space + 0.5*m1m2.second_layer_width + self.m1_rail_height
        for i in range(self.word_size):
            din_pin = self.ms_inst[i].get_pin("din")

            rail_y = self.min_y + i * rail_pitch

            double_via = contact.contact(layer_stack=contact.m1m2.layer_stack, dimensions=[1, 2])
            pin_via_offset = vector(din_pin.lx() + double_via.first_layer_height -
                                    double_via.first_layer_vertical_enclosure, rail_y)

            if i < self.word_size - 1:

                # via below din

                via_offset = vector(din_pin.cx(), - via_space - 0.5*m1m2.second_layer_width)
                self.add_contact_center(layers=m1m2_layers, offset=via_offset, rotate=90)

                # m2 to via
                offset = vector(din_pin.lx(), via_offset.y)

                self.add_rect("metal2", width=din_pin.width(), height=din_pin.by()-via_offset.y, offset=offset)

                # m1 to rail

                offset = vector(din_pin.lx(), rail_y)
                self.add_rect("metal1", offset=offset, width=din_pin.width(), height=via_offset.y-rail_y)

                # m2 via
                self.add_contact(layers=m1m2_layers, offset=pin_via_offset, size=[1, 2], rotate=90)

                # add metal 2, 3 for drc min area
                fill_width = self.metal1_minwidth_fill
                self.add_rect("metal2", vector(din_pin.cx(), rail_y), width=fill_width)
                self.add_rect("metal3", vector(din_pin.cx(), rail_y), width=fill_width)
            else:
                # connect directly
                offset = vector(din_pin.lx(), rail_y)
                fill_width = self.metal1_minwidth_fill
                fill_x_offset = min(self.width - fill_width, din_pin.cx())
                self.add_rect("metal3", vector(fill_x_offset, rail_y), width=fill_width)
                self.add_rect("metal2", width=din_pin.width(), height=din_pin.by() - rail_y, offset=offset)

            self.add_contact(layers=contact.m2m3.layer_stack, offset=pin_via_offset, size=[1, 2], rotate=90)
            self.add_contact(layers=contact.m3m4.layer_stack, offset=pin_via_offset, size=[1, 2], rotate=90)

            # add pin
            pin_offset = vector(din_pin.cx(), rail_y)
            pin_width = self.width - din_pin.cx()
            self.add_layout_pin(text="din[{}]".format(i), layer="metal4", offset=pin_offset, width=pin_width)


            dout_pin = self.ms_inst[i].get_pin("dout")

            rail_y = top_gnd_pin.uy() + 2*self.m1_space + m1m2.first_layer_width + i * rail_pitch
            if i == 0:
                # connect directly
                offset = vector(dout_pin.lx(), dout_pin.uy())
                self.add_rect("metal2", width=dout_pin.width(), height=rail_y - dout_pin.uy(), offset=offset)
            else:
                # m2 to via
                via_offset = vector(dout_pin.cx(), top_gnd_pin.uy() + self.m1_space + 0.5 * m1m2.first_layer_width)
                self.add_rect("metal2", width=dout_pin.width(), height=via_offset.y - dout_pin.uy(),
                              offset=dout_pin.ul())
                self.add_contact_center(layers=m1m2_layers, offset=via_offset, rotate=90)

                # m1 to rail
                offset = vector(dout_pin.lx(), via_offset.y)
                self.add_rect("metal1", offset=offset, width=din_pin.width(), height=rail_y - via_offset.y)

                via_offset = vector(dout_pin.cx(), rail_y + 0.5*self.m2_width)
                self.add_contact_center(layers=m1m2_layers, offset=via_offset, rotate=90)


            self.add_layout_pin(text="dout[{}]".format(i),
                                layer="metal2",
                                offset=vector(dout_pin.lx(), rail_y),
                                width=self.width-dout_pin.lx(),
                                height=self.m2_width)




            doutbar_pin = self.ms_inst[i].get_pin("dout_bar")
            self.add_layout_pin(text="dout_bar[{}]".format(i),
                                layer="metal2",
                                offset=doutbar_pin.ll(),
                                width=doutbar_pin.width(),
                                height=doutbar_pin.height())

            self.height = self.max_y - self.min_y
