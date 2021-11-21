from base.contact import m1m2, m2m3, cross_m2m3
from base.design import METAL1, METAL2, METAL3
from base.vector import vector
from modules.bitcell_vertical_aligned import BitcellVerticalAligned
from pgates.pinv import pinv
from pgates.pnand2 import pnand2


class DecoderLogic(BitcellVerticalAligned):
    """
    Implements in_0.en_0 + in_1.en_1 = NAND( (NAND(in_0, en_0), NAND(in_1, en_1) )
    """
    nand = None

    def __init__(self, num_rows):
        super().__init__("decoder_logic_{}".format(num_rows))

        self.num_rows = num_rows

        self.in_0_bar_insts = []
        self.in_1_bar_insts = []
        self.en_bar_insts = []

        self.add_pins()
        self.create_modules()
        self.calculate_y_offsets()
        self.create_array()

        self.width = self.en_bar_insts[-1].rx()
        self.height = self.en_bar_insts[-1].uy()

        self.add_layout_pins()

        self.route_layout()

    def add_pins(self):
        for row in range(self.num_rows):
            self.add_pin('in_0[{}]'.format(row))
            self.add_pin('in_1[{}]'.format(row))
            self.add_pin('out[{}]'.format(row))

        self.add_pin("en_1")
        self.add_pin_list(["vdd", "gnd"])

    def create_modules(self):
        self.create_bitcell()
        self.nand = pnand2(size=1, align_bitcell=True, same_line_inputs=True,
                           contact_nwell=False, contact_pwell=False)
        self.add_mod(self.nand)
        self.inv = pinv(size=1, align_bitcell=True, same_line_inputs=True,
                        contact_nwell=False, contact_pwell=False)
        self.add_mod(self.inv)

    def create_array(self):

        for row in range(self.num_rows):
            y_offset, mirror = self.get_row_y_offset(row)

            self.in_1_bar_insts.append(self.add_inst('in_1_{}'.format(row), mod=self.nand,
                                                     offset=vector(0, y_offset), mirror=mirror))
            self.connect_inst(["en_1", "in_1[{}]".format(row),
                               "in_1_bar[{}]".format(row), "vdd", "gnd"])

            x_offset = self.in_1_bar_insts[-1].rx()
            self.in_0_bar_insts.append(self.add_inst('in_0_{}'.format(row), mod=self.inv,
                                                     offset=vector(x_offset, y_offset),
                                                     mirror=mirror))
            self.connect_inst(["in_0[{}]".format(row), "in_0_bar[{}]".format(row), "vdd", "gnd"])

            x_offset = self.in_0_bar_insts[-1].rx()
            self.en_bar_insts.append(self.add_inst('en_bar_{}'.format(row), mod=self.nand,
                                                   offset=vector(x_offset, y_offset), mirror=mirror))
            self.connect_inst(["in_0_bar[{}]".format(row), "in_1_bar[{}]".format(row),
                               "out[{}]".format(row), "vdd", "gnd"])

    def get_bot_rail_y(self, row):
        return self.in_1_bar_insts[row].by() + 0.5 * self.rail_height

    def get_top_rail_y(self, row):
        return self.in_1_bar_insts[row].uy() - 0.5 * self.rail_height - self.m3_width

    def route_layout(self):
        module_insts = [self.in_1_bar_insts, self.in_0_bar_insts]
        en_pin = self.get_pin("en_1")

        fill_height = self.nand.gate_fill_height
        (fill_height, fill_width) = self.calculate_min_area_fill(fill_height, self.m2_width)

        for row in range(self.num_rows):
            for i in range(2):
                if i == 0:
                    # connect enable pin
                    a_pin = module_insts[i][row].get_pin("A")
                    self.add_rect(METAL1, offset=vector(en_pin.lx(),
                                                        a_pin.cy() - 0.5 * self.m1_width),
                                  width=a_pin.lx() - en_pin.lx())
                    self.add_contact_center(m1m2.layer_stack, offset=vector(en_pin.cx(), a_pin.cy()))
                    pin_name = "B"
                else:
                    pin_name = "A"
                in_pin = module_insts[i][row].get_pin(pin_name)
                self.add_contact_center(m1m2.layer_stack, offset=in_pin.center(), rotate=90)
                self.add_contact_center(m2m3.layer_stack, offset=in_pin.center())

                self.add_rect_center(METAL2, offset=in_pin.center(), width=fill_width,
                                     height=fill_height)

                if i == 0:
                    pin_name = f"in_1[{row}]"
                    y_offset = self.get_bot_rail_y(row)
                else:
                    pin_name = f"in_0[{row}]"
                    y_offset = self.get_top_rail_y(row)
                self.add_rect(METAL3, offset=vector(in_pin.cx() - 0.5 * self.m3_width, in_pin.cy()),
                              height=y_offset - in_pin.cy())

                self.add_layout_pin(pin_name, METAL3, offset=vector(0, y_offset),
                                    width=in_pin.cx() + 0.5 * self.m3_width)
            self.route_en_0_output(row)
            self.route_en_1_output(row, fill_width, fill_height)

    def route_en_0_output(self, row):
        # route en_0 output to en_insts a pin
        a_pin = self.en_bar_insts[row].get_pin("A")
        z_pin = self.in_0_bar_insts[row].get_pin("Z")
        self.add_rect(METAL1, offset=vector(z_pin.rx(), a_pin.cy() - 0.5 * self.m1_width),
                      width=a_pin.lx() - z_pin.rx())

    def route_en_1_output(self, row, fill_width, fill_height):
        # route en_1 output to en_insts b pin
        z_pin = self.in_1_bar_insts[row].get_pin("Z")
        b_pin = self.en_bar_insts[row].get_pin("B")

        y_offset = self.get_bot_rail_y(row)
        x_offset = z_pin.cx() - 0.5 * self.m2_width
        self.add_rect(METAL2, offset=vector(x_offset, y_offset), height=z_pin.by() - y_offset)
        self.add_cross_contact_center(cross_m2m3, vector(z_pin.cx(), y_offset + 0.5 * self.m3_width))

        self.add_rect(METAL3, offset=vector(x_offset, y_offset), width=b_pin.cx() - x_offset)
        self.add_rect(METAL3, offset=vector(b_pin.cx() - 0.5 * self.m3_width, y_offset),
                      height=b_pin.cy() - y_offset)
        self.add_contact_center(m1m2.layer_stack, offset=b_pin.center(), rotate=90)
        self.add_contact_center(m2m3.layer_stack, offset=b_pin.center())

        self.add_rect_center(METAL2, offset=b_pin.center(), width=fill_width,
                             height=fill_height)

    def add_layout_pins(self):
        # enable pin
        x_offset = self.in_1_bar_insts[0].lx() + self.m1_space
        self.add_layout_pin("en_1", METAL2, offset=vector(x_offset, 0),
                            height=self.height)

        for row in range(self.num_rows):
            self.copy_layout_pin(self.en_bar_insts[row], "Z", "out[{}]".format(row))
            self.copy_layout_pin(self.en_bar_insts[row], "vdd", "vdd".format(row))
            self.copy_layout_pin(self.en_bar_insts[row], "gnd", "gnd".format(row))

    def add_body_taps(self):
        self._add_body_taps(self.in_1_bar_insts[0], self.in_1_bar_insts)
