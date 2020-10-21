from base import utils
from base.contact import contact, m1m2, m2m3
from base.design import NWELL, PIMP, METAL1, METAL2, METAL3
from base.utils import round_to_grid
from base.vector import vector
from globals import OPTS
from modules.precharge import precharge
from pgates.ptx import ptx
from tech import parameter


class sotfet_mram_precharge(precharge):

    def create_layout(self):
        self.set_layout_constants()
        self.create_ptx()
        self.add_ptx_inst()

        self.connect_input_gates()
        self.connect_bl()
        self.add_vdd_pin()
        self.height = self.get_pin("vdd").uy()

        self.add_bitline_pins()
        self.fill_nwell()

    def create_ptx(self):
        num_fingers = OPTS.precharge_num_fingers
        self.ptx_width = utils.ceil(max(parameter["min_tx_size"], self.ptx_width / num_fingers))
        self.pmos = ptx(width=self.ptx_width, mults=num_fingers, tx_type="pmos")
        self.pmos.translate_all(self.pmos.active_offset.scale(-1, -1))

    def add_ptx_inst(self):

        # find middle of active
        active_rect = self.pmos.get_layer_shapes("active")[0]
        active_mid_x = 0.5 * (active_rect.lx() + active_rect.rx())

        implant_bottom = self.pmos.get_layer_shapes(PIMP)[0].by()
        x_offset = 0.5 * self.width - active_mid_x

        self.ptx_inst = self.add_inst(name="bl_pmos", mod=self.pmos,
                                      offset=vector(x_offset, -implant_bottom))
        self.connect_inst(["bl", "en", "vdd", "vdd"])

    def connect_bl(self):
        # first assume worst case fill width for initial fill width estimate
        metal_fill_width = round_to_grid(2 * (self.poly_pitch - 0.5 * self.m1_width - self.m1_space))
        m1_space = self.get_space_by_width_and_length(METAL1, max_width=metal_fill_width,
                                                      min_width=self.m1_width, run_length=self.ptx_width)
        # actual fill width estimate
        metal_fill_width = round_to_grid(2 * (self.poly_pitch - 0.5 * self.m1_width - m1_space))

        # create dummy contact to measure contact height
        active_cont = contact(layer_stack=contact.active_layers, dimensions=[1, self.pmos.num_contacts])

        metal_fill_height = utils.ceil(max(self.minarea_metal1_contact / metal_fill_width,
                                           active_cont.first_layer_height))

        source_pins = self.ptx_inst.get_pins("S")
        self.max_fill_y = max(source_pins[0].uy(), source_pins[0].cy() + 0.5 * m1m2.height)
        for pin in source_pins:
            x_offset = pin.cx() - 0.5 * metal_fill_width
            y_offset = pin.cy() - 0.5 * max(self.ptx_width, m1m2.height)
            self.max_fill_y = max(self.max_fill_y, y_offset + metal_fill_height)

            y_offset = self.max_fill_y - metal_fill_height

            if len(self.ptx_inst.get_pins("S")) == 1:
                fill_layers = [METAL1, METAL2]
            else:
                fill_layers = [METAL1]
            for fill_layer in fill_layers:
                self.add_rect(fill_layer, offset=vector(x_offset, y_offset),
                              width=metal_fill_width, height=metal_fill_height)
            self.add_contact_center(m1m2.layer_stack, offset=pin.center())

        if len(source_pins) > 1:
            left_most = min(source_pins, key=lambda x: x.lx())
            right_most = max(source_pins, key=lambda x: x.rx())
            self.add_rect(METAL2, offset=vector(left_most.cx(), left_most.cy() - 0.5 * self.m2_width),
                          width=right_most.cx() - left_most.cx())

    def connect_input_gates(self):
        gate_pin = self.ptx_inst.get_pins("G")[0]
        self.add_layout_pin("en", METAL1, offset=vector(0, gate_pin.cy() - 0.5 * self.m1_width),
                            width=self.width)

    def add_vdd_pin(self):
        pin_height = self.rail_height
        y_offset = self.max_fill_y + self.get_line_end_space(METAL2)
        self.add_layout_pin("vdd", METAL1, offset=vector(0, y_offset),
                            height=pin_height, width=self.width)
        via_y = self.get_pin("vdd").cy()
        self.add_contact_center(m1m2.layer_stack, offset=vector(self.mid_x, via_y),
                                size=[1, 2], rotate=90)
        cont = self.add_contact_center(m2m3.layer_stack, offset=vector(self.mid_x, via_y),
                                       size=[1, 2], rotate=90)
        self.add_rect_center(METAL2, offset=vector(self.mid_x, via_y),
                             height=pin_height, width=cont.height)
        self.add_rect(METAL3, offset=vector(0, y_offset), width=self.width, height=pin_height)

        for pin in self.ptx_inst.get_pins("D"):
            self.add_rect(METAL1, offset=pin.ul(), width=pin.width(),
                          height=self.get_pin("vdd").by() - pin.uy())

    def add_bitline_pins(self):
        for pin_name in ["BL", "BR"]:
            bitcell_pin = self.bitcell.get_pin(pin_name)
            self.add_layout_pin(pin_name.lower(), bitcell_pin.layer, offset=vector(bitcell_pin.lx(), 0),
                                height=self.height, width=bitcell_pin.width())

        bl_pin = self.get_pin("bl")
        tx_source = self.ptx_inst.get_pins("S")[0]

        wide_space = self.get_wide_space(METAL2)
        if bl_pin.rx() < tx_source.lx():
            if tx_source.lx() - bl_pin.rx() > wide_space:
                fill_height = self.m2_width
            else:
                fill_height = m1m2.height
            self.add_rect(METAL2, offset=vector(bl_pin.cx(), tx_source.cy() - 0.5 * fill_height),
                          width=tx_source.cx() - bl_pin.cx(), height=fill_height)

    def fill_nwell(self):
        layers = [NWELL, PIMP]
        purposes = ["drawing", "drawing"]
        for i in range(len(layers)):
            existing_rect = self.pmos.get_layer_shapes(layers[i], purposes[i])[0]
            left_extension = - existing_rect.lx()
            right_extension = existing_rect.rx() - self.pmos.width
            x_offset = min(0, self.ptx_inst.lx() - left_extension)
            right = max(self.width, self.ptx_inst.rx() + right_extension)

            rect_bottom = min(self.ptx_inst.by() + existing_rect.by(), 0)
            rect_top = max(rect_bottom + existing_rect.height, self.height)

            self.add_rect(layers[i], offset=vector(x_offset, rect_bottom),
                          height=rect_top - rect_bottom,
                          width=right - x_offset)
