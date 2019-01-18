from base import contact
from base import design
from base import utils
from base.vector import vector
from modules.signal_gate import SignalGate
from pgates.pinv import pinv
from pgates.pnand2 import pnand2


class WwlDriver(SignalGate):

    def get_name(self):
        return "wwl_driver"

    def route_input_pins(self):
        # en pin
        b_pin = self.logic_inst.get_pin("B")
        offset = vector(b_pin.lx(), b_pin.uy() - contact.m1m2.second_layer_height)
        self.add_contact(contact.m1m2.layer_stack, offset)
        self.add_rect("metal2", offset=vector(0, b_pin.uy() - self.m2_width), width=b_pin.lx())
        self.add_layout_pin("en", "metal2", offset=vector(0, 0), height=self.logic_inst.height)

        # in pin
        a_pin = self.logic_inst.get_pin("A")
        offset = vector(a_pin.rx(), a_pin.cy() - 0.5*contact.m1m2.second_layer_height)
        self.add_contact(contact.m1m2.layer_stack, offset=offset, rotate=90)
        self.add_contact(contact.m2m3.layer_stack, offset=offset, rotate=90)
        # add m2 fill
        fill_width = utils.ceil(self.minarea_metal1_minwidth/contact.m2m3.second_layer_height)
        self.add_rect("metal2", vector(self.m2_width + self.line_end_space, offset.y), width=fill_width)
        self.add_layout_pin("in", "metal3", offset=vector(0, offset.y), width=a_pin.lx())

    def add_out_pins(self):
        self.copy_layout_pin(self.module_insts[-2], "Z", "out_inv")
        self.copy_layout_pin(self.module_insts[-1], "Z", "out")

    def create_buffer_inv(self, size):
        return pinv(size=size, align_bitcell=True)

    def create_logic_mod(self):
        self.logic_mod = pnand2(1, align_bitcell=True, same_line_inputs=False)


class WwlDriverArray(design.design):
    def __init__(self, rows, buffer_stages, no_cols=16):
        design.design.__init__(self, "wwl_driver_array")

        self.rows = rows
        self.buffer_stages = buffer_stages
        self.no_cols = no_cols
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
            self.add_pin("wwl[{0}]".format(i))
        self.add_pin("en")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_layout(self):
        self.add_driver_array()
        self.width = self.module_insts[0].rx()
        self.height = self.module_insts[-1].uy()
        self.add_layout_pins()

    def add_driver_array(self):
        self.driver_mod = driver_mod = WwlDriver(self.buffer_stages, contact_pwell=False, contact_nwell=False)
        self.add_mod(driver_mod)
        for row in range(self.rows):
            y_offset = row*driver_mod.height
            mirror = "R0"
            if row % 2 == 0:
                y_offset += driver_mod.height
                mirror = "MX"
            self.module_insts.append(self.add_inst("driver[{}]".format(row), mod=driver_mod, offset=vector(0, y_offset),
                                                   mirror=mirror))
            self.connect_inst(["en", "in[{}]".format(row), "wwl[{}]".format(row),
                               "wwl_bar[{}]".format(row), "vdd", "gnd"])

    def add_layout_pins(self):

        self.add_layout_pin("en", "metal2", offset=vector(0, 0), height=self.height)

        for i in range(self.rows):
            inst = self.module_insts[i]
            self.copy_layout_pin(inst, "out", "wwl[{}]".format(i))
            self.copy_layout_pin(inst, "in", "in[{}]".format(i))

        for inst in set(self.module_insts[::2] + [self.module_insts[-1]]):
            self.copy_layout_pin(inst, "vdd", "vdd")
            self.copy_layout_pin(inst, "gnd", "gnd")

