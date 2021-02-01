from base import contact
from base import design
from base.contact import m1m2
from base.vector import vector
from globals import OPTS
from modules.logic_buffer import LogicBuffer


class wordline_driver_array(design.design):
    """
    Creates a Wordline Driver using LogicBuffer cells
    Re-write of existing wordline_driver supporting drive strength configurability
    buffer_stages: configure buffer stages, number of stages should be odd
    Generates the wordline-driver to drive the bitcell
    """

    logic_buffer = None

    inv1 = None

    def __init__(self, rows, buffer_stages=None):
        design.design.__init__(self, "wordline_driver")

        self.rows = rows
        if buffer_stages is None:
            buffer_stages = [2, 8]
        self.buffer_stages = buffer_stages

        self.buffer_insts = []
        self.module_insts = []

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_pins(self):
        # inputs to wordline_driver.
        for i in range(self.rows):
            self.add_pin("in[{0}]".format(i))
        # Outputs from wordline_driver.
        for i in range(self.rows):
            self.add_pin("wl[{0}]".format(i))
        self.add_pin("en")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_layout(self):
        self.create_modules()
        self.add_modules()

        self.width = self.buffer_insts[0].rx()
        self.inv1 = self.logic_buffer.buffer_mod.buffer_invs[0]
        self.module_insts = self.logic_buffer.buffer_mod.module_insts

    def create_modules(self):
        c = __import__(OPTS.bitcell)
        mod_bitcell = getattr(c, OPTS.bitcell)
        bitcell = mod_bitcell()

        self.logic_buffer = LogicBuffer(self.buffer_stages, logic="pnand2", height=bitcell.height, route_outputs=False,
                                        route_inputs=False,
                                        contact_pwell=False, contact_nwell=False, align_bitcell=True)
        self.add_mod(self.logic_buffer)

    def add_modules(self):
        en_pin_x = self.m1_space + self.m1_width
        in_pin_width = en_pin_x + self.m2_width + self.parallel_line_space
        m1m2_via_x = in_pin_width + contact.m1m2.first_layer_width
        x_offset = m1m2_via_x + self.m2_space + 0.5*contact.m1m2.first_layer_width

        self.height = self.logic_buffer.height * self.rows

        en_pin = self.add_layout_pin(text="en",
                                     layer="metal2",
                                     offset=[en_pin_x, 0],
                                     width=self.m2_width,
                                     height=self.height)

        for row in range(self.rows):
            if (row % 2) == 0:
                y_offset = self.logic_buffer.height*(row + 1)
                mirror = "MX"

            else:
                y_offset = self.logic_buffer.height*row
                mirror = "R0"
            # add logic buffer
            buffer_inst = self.add_inst("driver{}".format(row), mod=self.logic_buffer,
                                        offset=vector(x_offset, y_offset), mirror=mirror)
            self.connect_inst(["en", "in[{}]".format(row), "wl_bar[{}]".format(row), "wl[{}]".format(row),  "vdd",
                               "gnd"])
            self.buffer_insts.append(buffer_inst)

            # route en input pin
            a_pin = buffer_inst.get_pin("A")
            a_pos = a_pin.lc()
            clk_offset = vector(en_pin.bc().x, a_pos.y)
            self.add_segment_center(layer="metal1",
                                    start=clk_offset,
                                    end=a_pos)
            self.add_via(layers=m1m2.layer_stack,
                         offset=vector(en_pin.lx() + m1m2.second_layer_height,
                                       a_pin.cy() - 0.5 * self.m2_width),
                         rotate=90)

            # route in pin
            self.copy_layout_pin(buffer_inst, "B", "in[{}]".format(row))

            # output each WL on the right
            self.copy_layout_pin(buffer_inst, "out", "wl[{0}]".format(row))

            # Extend vdd and gnd of wordline_driver
            y_offset = (row + 1) * self.logic_buffer.height - 0.5 * self.rail_height
            if (row % 2) == 0:
                pin_name = "gnd"
            else:
                pin_name = "vdd"

            self.add_layout_pin(text=pin_name, layer="metal1", offset=[0, y_offset],
                                width=buffer_inst.rx(),
                                height=self.rail_height)
        # add vdd for row zero
        self.add_layout_pin(text="vdd", layer="metal1",
                            offset=[0, -0.5*self.rail_height], width=self.buffer_insts[0].rx(),
                            height=self.rail_height)

    def analytical_delay(self, slew, load=0):
        return self.logic_buffer.analytical_delay(slew, load)

    def input_load(self):
        return self.logic_buffer.logic_mod.input_load()
