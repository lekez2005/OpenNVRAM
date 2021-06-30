from base.contact import m1m2, m2m3
from base.design import design
from base.vector import vector
from pgates.pnand2 import pnand2


class DecoderLogic(design):
    """
    Implements in_0.en_0 + in_1.en_1 = NAND( (NAND(in_0, en_0), NAND(in_1, en_1) )
    """
    nand = None

    def __init__(self, num_rows):
        super().__init__("decoder_logic_{}".format(num_rows))

        self.num_rows = num_rows

        self.en_0_insts = []
        self.en_1_insts = []
        self.en_insts = []

        self.add_pins()
        self.create_modules()
        self.create_array()

        self.width = self.en_insts[-1].rx()
        self.height = self.en_insts[-1].uy()

        self.add_layout_pins()

        self.route()

    def add_pins(self):
        for row in range(self.num_rows):
            self.add_pin('in_0[{}]'.format(row))
            self.add_pin('in_1[{}]'.format(row))
            self.add_pin('out[{}]'.format(row))

        self.add_pin("en_0")
        self.add_pin("en_1")
        self.add_pin_list(["vdd", "gnd"])

    def create_modules(self):
        self.nand = pnand2(size=1, align_bitcell=True, contact_nwell=False, contact_pwell=False)
        self.add_mod(self.nand)

    def create_array(self):
        for row in range(self.num_rows):
            if row % 2 == 0:
                y_offset = self.nand.height*(row + 1)
                mirror = "MX"
            else:
                y_offset = self.nand.height*row
                mirror = "R0"

            self.en_1_insts.append(self.add_inst('en_1_{}'.format(row), mod=self.nand, offset=vector(0, y_offset),
                                                 mirror=mirror))
            self.connect_inst(["en_1", "in_1[{}]".format(row), "en_1[{}]".format(row), "vdd", "gnd"])

            x_offset = self.en_1_insts[-1].rx()
            self.en_0_insts.append(self.add_inst('en_0_{}'.format(row), mod=self.nand,
                                                 offset=vector(x_offset, y_offset), mirror=mirror))
            self.connect_inst(["en_0", "in_0[{}]".format(row), "en_0[{}]".format(row), "vdd", "gnd"])

            x_offset = self.en_0_insts[-1].rx()
            self.en_insts.append(self.add_inst('en_{}'.format(row), mod=self.nand,
                                               offset=vector(x_offset, y_offset), mirror=mirror))
            self.connect_inst(["en_0[{}]".format(row), "en_1[{}]".format(row), "out[{}]".format(row), "vdd", "gnd"])

    def route(self):
        module_insts = [self.en_1_insts, self.en_0_insts]
        en_pins = [self.get_pin("en_1"), self.get_pin("en_0")]

        fill_height = m2m3.second_layer_height + self.m2_width
        (height, width) = self.calculate_min_area_fill(fill_height, self.m2_width)

        for row in range(self.num_rows):
            for i in range(2):
                en_pin = en_pins[i]
                a_pin = module_insts[i][row].get_pin("A")
                self.add_rect("metal1", offset=vector(en_pin.lx(), a_pin.cy()-0.5*self.m1_width),
                              width=a_pin.lx()-en_pin.lx())
                self.add_contact_center(m1m2.layer_stack, offset=vector(en_pin.cx(), a_pin.cy()))

                b_pin = module_insts[i][row].get_pin("B")
                self.add_contact_center(m1m2.layer_stack, offset=b_pin.center())
                self.add_contact_center(m2m3.layer_stack, offset=b_pin.center())

                self.add_rect_center("metal2", offset=b_pin.center(), width=width, height=height)

                if row % 2 == 0:
                    y_offset = module_insts[i][row].by() + 0.5*self.rail_height
                else:
                    y_offset = module_insts[i][row].uy() - 0.5*self.rail_height - self.m3_width
                self.add_rect("metal3", offset=vector(b_pin.lx(), b_pin.cy()), height=y_offset-b_pin.cy())

                if i == 0:
                    self.add_layout_pin("in_1[{}]".format(row), "metal3", offset=vector(0, y_offset),
                                        width=b_pin.rx())
                else:
                    self.add_layout_pin("in_0[{}]".format(row), "metal3", offset=vector(b_pin.lx(), y_offset),
                                        width=self.width-b_pin.lx())

            # route en_0 output to en_insts a pin
            a_pin = self.en_insts[row].get_pin("A")
            z_pin = self.en_0_insts[row].get_pin("Z")
            self.add_rect("metal1", offset=vector(z_pin.rx(), a_pin.cy()-0.5*self.m1_width),
                          width=a_pin.lx()-z_pin.rx())

            # route en_1 output to en_insts b pin
            z_pin = self.en_1_insts[row].get_pin("Z")
            b_pin = self.en_insts[row].get_pin("B")
            if row % 2 == 1:
                y_offset = self.en_insts[row].by() + 0.5 * self.rail_height
                m2_start = z_pin.uy()
                self.add_contact(m2m3.layer_stack, offset=vector(z_pin.lx(), y_offset))

            else:
                y_offset = self.en_insts[row].uy() - 0.5 * self.rail_height - self.m3_width
                m2_start = z_pin.by()
                self.add_contact(m2m3.layer_stack, offset=vector(z_pin.lx(),
                                                                 y_offset + self.m2_width - m2m3.second_layer_height))

            self.add_rect("metal2", offset=vector(z_pin.lx(), m2_start), height=y_offset-m2_start)

            self.add_rect("metal3", offset=vector(z_pin.lx(), y_offset), width=b_pin.rx()-z_pin.lx())
            self.add_rect("metal3", offset=vector(b_pin.cx()-0.5*self.m3_width, b_pin.cy()),
                          height=y_offset-b_pin.cy())
            self.add_contact_center(m1m2.layer_stack, offset=b_pin.center())
            self.add_contact_center(m2m3.layer_stack, offset=b_pin.center())

            self.add_rect_center("metal2", offset=b_pin.center(), width=width, height=height)

    def add_layout_pins(self):
        # enable pins
        pin_names = ["en_0", "en_1"]
        module_insts = [self.en_0_insts[0], self.en_1_insts[1]]
        for i in range(2):
            module_inst = module_insts[i]
            x_offset = module_inst.lx() + self.m1_space
            self.add_layout_pin(pin_names[i], "metal2", offset=vector(x_offset, 0),
                                height=self.height)

        for row in range(self.num_rows):
            self.copy_layout_pin(self.en_insts[row], "Z", "out[{}]".format(row))
            self.copy_layout_pin(self.en_insts[row], "vdd", "vdd".format(row))
            self.copy_layout_pin(self.en_insts[row], "gnd", "gnd".format(row))

