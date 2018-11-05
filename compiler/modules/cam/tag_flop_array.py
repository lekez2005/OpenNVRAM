import contact
import design
import debug
from globals import OPTS
from vector import vector


class tag_flop_array(design.design):
    """
    Array of 2-1 mux to decide between address decoder output and match tags for enabling wordline driver
    """

    def __init__(self, rows):
        design.design.__init__(self, "tag_flops_array")
        debug.info(1, "Creating {0}".format(self.name))

        c = reload(__import__(OPTS.ms_flop_horz_pitch))
        self.mod_ms_flop = getattr(c, OPTS.ms_flop_horz_pitch)
        self.flop = self.mod_ms_flop()
        self.add_mod(self.flop)

        self.rows = rows
        self.flop_insts = []

        self.width = self.flop.width
        self.height = self.height = self.rows * self.flop.height


        self.add_pins()
        self.create_layout()
        self.add_layout_pins()
        self.DRC_LVS()

    def add_pins(self):
        for i in range(self.rows):
            self.add_pin("din[{0}]".format(i))
        for i in range(self.rows):
            self.add_pin("dout[{0}]".format(i))
            self.add_pin("dout_bar[{0}]".format(i))
        self.add_pin("clk")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_layout(self):

        for row in range(self.rows):
            y_offset = row * self.flop.height
            if row % 2 == 0:
                y_offset += self.flop.height
                mirror = "MX"
            else:
                mirror = "R0"
            name = "precharge_{}".format(row)
            offset = vector(0, y_offset)
            self.flop_insts.append(self.add_inst(name=name, mod=self.flop, offset=offset, mirror=mirror))

            self.connect_inst(["din[{0}]".format(row),
                               "dout[{0}]".format(row),
                               "dout_bar[{0}]".format(row),
                               "clk",
                               "vdd", "gnd"])

    def add_layout_pins(self):

        clk_x_offset = self.flop.get_pin("clk").lx() - self.line_end_space - self.m2_width

        for row in range(self.rows):
            inst = self.flop_insts[row]
            self.copy_layout_pin(inst, "din", "din[{0}]".format(row))
            self.copy_layout_pin(inst, "dout", "dout[{0}]".format(row))
            self.copy_layout_pin(inst, "dout_bar", "dout_bar[{0}]".format(row))
            clk_pin = inst.get_pin("clk")
            self.add_rect("metal1", offset=vector(clk_x_offset, clk_pin.by()), width=clk_pin.lx() - clk_x_offset)
            self.add_contact_center(contact.m1m2.layer_stack,
                                    offset=vector(clk_x_offset + 0.5*contact.m1m2.second_layer_width, clk_pin.cy()))
            if row % 2 == 0 or row == self.rows - 1:
                self.copy_layout_pin(inst, "vdd", "vdd")
                self.copy_layout_pin(inst, "gnd", "gnd")
        self.add_layout_pin("clk", "metal2", offset=vector(clk_x_offset, 0), height=self.height)

