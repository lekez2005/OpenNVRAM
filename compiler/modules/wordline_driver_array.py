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

    def __init__(self, rows, buffer_stages, name=None):
        if name is None:
            name = "wordline_driver"
        design.design.__init__(self, name)

        self.rows = rows
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
        self.bitcell = self.create_mod_from_str(OPTS.bitcell)

        self.logic_buffer = LogicBuffer(self.buffer_stages, logic="pnand2", height=self.bitcell.height,
                                        route_outputs=False, route_inputs=False,
                                        contact_pwell=False, contact_nwell=False, align_bitcell=True)
        self.add_mod(self.logic_buffer)

    def calculate_y_offsets(self):
        bitcell_array_cls = self.import_mod_class_from_str(OPTS.bitcell_array)
        offsets = bitcell_array_cls.calculate_y_offsets(num_rows=self.rows)
        self.bitcell_offsets, self.tap_offsets, self.dummy_offsets = offsets
        self.height = max(self.bitcell_offsets + self.dummy_offsets) + self.bitcell.height

    def get_row_y_offset(self, row):
        y_offset = self.bitcell_offsets[row]
        if (row % 2) == 0:
            y_offset += self.logic_buffer.height
            mirror = "MX"
        else:
            mirror = "R0"
        return y_offset, mirror

    def route_en_pin(self, buffer_inst, en_pin):
        # route en input pin
        a_pin = buffer_inst.get_pin("A")
        a_pos = a_pin.lc()
        clk_offset = vector(en_pin.cx(), a_pos.y)
        self.add_segment_center(layer="metal1",
                                start=clk_offset,
                                end=a_pos)
        self.add_via(layers=m1m2.layer_stack,
                     offset=vector(en_pin.lx() + m1m2.second_layer_height,
                                   a_pin.cy() - 0.5 * self.m2_width),
                     rotate=90)

    def get_height(self):
        return self.logic_buffer.height * self.rows

    def add_en_pin(self):
        en_pin_x = self.m1_space + self.m1_width
        en_pin = self.add_layout_pin(text="en",
                                     layer="metal2",
                                     offset=[en_pin_x, 0],
                                     width=self.m2_width,
                                     height=self.get_height())
        return en_pin, en_pin_x

    def add_in_pin(self, buffer_inst, row):
        # route in pin
        self.copy_layout_pin(buffer_inst, "B", "in[{}]".format(row))

    def get_buffer_x_offset(self, en_pin_x):
        in_pin_width = en_pin_x + self.m2_width + self.parallel_line_space
        m1m2_via_x = in_pin_width + contact.m1m2.first_layer_width
        x_offset = m1m2_via_x + self.m2_space + 0.5 * contact.m1m2.first_layer_width
        return x_offset

    def add_modules(self):
        self.calculate_y_offsets()

        en_pin, en_pin_x = self.add_en_pin()
        x_offset = self.get_buffer_x_offset(en_pin_x)

        self.height = self.get_height()

        for row in range(self.rows):
            y_offset, mirror = self.get_row_y_offset(row)

            # add logic buffer
            buffer_inst = self.add_inst("mod_{}".format(row), mod=self.logic_buffer,
                                        offset=vector(x_offset, y_offset), mirror=mirror)
            self.connect_inst(["en", "in[{}]".format(row), "wl_bar[{}]".format(row), "wl[{}]".format(row),  "vdd",
                               "gnd"])
            self.buffer_insts.append(buffer_inst)

            self.route_en_pin(buffer_inst, en_pin)

            self.add_in_pin(buffer_inst, row)

            # output each WL on the right
            self.copy_layout_pin(buffer_inst, "out", "wl[{0}]".format(row))

            # Extend vdd and gnd of wordline_driver
            for pin_name in ["vdd", "gnd"]:
                power_pin = buffer_inst.get_pin(pin_name)
                self.add_layout_pin(text=pin_name, layer=power_pin.layer,
                                    offset=[0, power_pin.by()],
                                    width=buffer_inst.rx(),
                                    height=power_pin.height())


    def analytical_delay(self, slew, load=0):
        return self.logic_buffer.analytical_delay(slew, load)

    def input_load(self):
        return self.logic_buffer.logic_mod.input_load()
