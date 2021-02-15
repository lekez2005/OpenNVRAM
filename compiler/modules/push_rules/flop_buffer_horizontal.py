from base.contact import m1m2, m2m3
from base.design import NIMP, METAL2, METAL3, PO_DUMMY
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from modules.flop_buffer import FlopBuffer
from modules.push_rules.buffer_stages_horizontal import BufferStagesHorizontal
from modules.push_rules.pgate_horizontal_tap import pgate_horizontal_tap


class FlopBufferHorizontal(FlopBuffer):
    rotation_for_drc = GDS_ROT_270

    @classmethod
    def get_name(cls, flop_module_name, buffer_stages, dummy_indices=None,
                 negate=False):
        name = super().get_name(flop_module_name, buffer_stages, negate)
        if cls.has_dummy and dummy_indices is not None:
            name += "_d" + "".join(map(str, dummy_indices))
        return name

    def __init__(self, flop_module_name, buffer_stages, dummy_indices=None, negate=False):
        self.dummy_indices = dummy_indices
        super().__init__(flop_module_name, buffer_stages, negate)

    def create_modules(self):
        self.flop = self.create_mod_from_str(self.flop_module_name, rotation=GDS_ROT_270)
        self.buffer = BufferStagesHorizontal(self.buffer_stages)
        self.add_mod(self.buffer)
        self.body_tap = pgate_horizontal_tap(self.buffer.buffer_invs[0])
        self.add_mod(self.body_tap)

    def add_modules(self):
        # add flop
        self.flop_inst = self.add_inst("flop", mod=self.flop, offset=vector(0, 0))
        self.connect_inst(["din", "flop_out", "flop_out_bar", "clk", "vdd", "gnd"])
        # add tap
        flop_implant = max(self.flop.get_layer_shapes(NIMP), key=lambda x: x.rx())
        buffer_implant = min(self.body_tap.get_layer_shapes(NIMP), key=lambda x: x.lx())

        implant_space = self.get_wide_space(NIMP)
        x_offset = (self.flop_inst.rx() + (flop_implant.rx() - self.flop_inst.width) -
                    buffer_implant.lx() + implant_space)
        self.tap_inst = self.add_inst(self.body_tap.name, self.body_tap,
                                      offset=vector(x_offset, 0))
        self.connect_inst([])
        # add buffer
        self.buffer_inst = self.add_inst("buffer", mod=self.buffer,
                                         offset=self.tap_inst.lr())
        flop_out = self.connect_buffer()
        # connect flop out to buffer in
        buffer_in = self.buffer_inst.get_pin("in")
        via_y = min(max(flop_out.cy() - 0.5 * m1m2.height, buffer_in.by()),
                    buffer_in.uy() - m1m2.height)
        self.add_rect(METAL2, offset=flop_out.lr(), width=buffer_in.rx() - flop_out.rx())
        if abs(flop_out.by() - via_y) > self.m2_width:
            self.add_rect(METAL2, offset=vector(buffer_in.lx(), flop_out.by()),
                          height=via_y - flop_out.by())
        self.add_contact(m1m2.layer_stack, offset=vector(buffer_in.lx(), via_y))

        self.width = self.buffer_inst.rx()
        self.height = self.buffer_inst.height

    def fill_layers(self):
        if not self.has_dummy:
            return
        if self.dummy_indices is None:
            self.dummy_indices = list(range(4))
        dummy_polys = self.flop.get_poly_fills(self.flop.child_mod)
        all_rects = [None] * 4
        all_rects[:len(dummy_polys["left"])] = dummy_polys["left"]
        all_rects[2:2 + len(dummy_polys["right"])] = dummy_polys["right"]
        for i in range(4):
            rect = all_rects[i]
            if i not in self.dummy_indices or not rect:
                continue
            y_offset = rect[0][0]
            x_offset = 0.5 * self.poly_to_field_poly
            width = self.flop_inst.width - x_offset
            self.add_rect(PO_DUMMY, offset=vector(x_offset, y_offset), width=width,
                          height=self.poly_width)

    def add_power_layout_pins(self):
        for pin_name in ["vdd", "gnd"]:
            buffer_pin = self.buffer_inst.get_pin(pin_name)
            flop_pin = self.flop_inst.get_pin(pin_name)
            via_span = self.m3_width + m1m2.width
            x_offset = self.tap_inst.lx() + via_span

            self.add_rect(METAL3, offset=flop_pin.lr(), width=x_offset - flop_pin.rx(),
                          height=flop_pin.height())
            via_offset = vector(x_offset - 0.5 * via_span, buffer_pin.cy())
            self.add_contact_center(m1m2.layer_stack, offset=via_offset)
            self.add_contact_center(m2m3.layer_stack, offset=via_offset)
            fill_height = m2m3.height
            fill_height, fill_width = self.calculate_min_area_fill(fill_height,
                                                                   layer=METAL2)
            self.add_rect_center(METAL2, offset=via_offset, width=fill_width,
                                 height=fill_height)
            self.copy_layout_pin(self.buffer_inst, pin_name)
