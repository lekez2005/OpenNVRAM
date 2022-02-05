import debug
from base import utils
from base.analog_cell_mixin import AnalogMixin
from base.contact import m1m2, poly_contact, cross_m1m2, cross_m2m3, m2m3
from base.design import design, METAL3, METAL2, METAL1, ACTIVE
from base.geometry import MIRROR_X_AXIS
from base.vector import vector
from base.well_active_contacts import calculate_num_contacts
from base.well_implant_fills import calculate_tx_metal_fill
from globals import OPTS
from modules.precharge import precharge_characterization
from pgates.ptx import ptx
from pgates.ptx_spice import ptx_spice


class BlBrReset(precharge_characterization, design):
    def __init__(self, name, size):
        design.__init__(self, name)
        self.size = size
        debug.info(2, "Create %s with size %.3g", self.name, size)
        self.create_layout()

    def create_layout(self):
        self.create_ptx()
        self.add_ptx_inst()
        self.create_netlist()
        self.add_enables()
        self.fill_drain_m1()
        self.add_gnd_pins()
        self.connect_bitlines()
        self.connect_gnd_pins()
        self.add_boundary()

    def create_netlist(self):
        self.add_pin_list(["bl", "br", "bl_reset", "br_reset", "gnd"])
        tx = self.ptx_inst.mod
        tx_spice = ptx_spice(width=tx.tx_width, mults=2,
                             tx_type=tx.tx_type, tx_length=tx.tx_length)
        self.add_mod(tx_spice)

        self.add_inst("bl", tx_spice, vector(0, 0))
        self.connect_inst(["bl", "bl_reset", "gnd", "gnd"])

        self.add_inst("br", tx_spice, vector(0, 0))
        self.connect_inst(["br", "br_reset", "gnd", "gnd"])

    def get_sorted_pins(self, pin_name):
        return AnalogMixin.get_sorted_pins(self.ptx_inst, pin_name)

    def create_ptx(self):
        self.bitcell = self.create_mod_from_str(OPTS.bitcell)
        self.width = self.bitcell.width
        self.mid_x = utils.round_to_grid(0.5 * self.width)

        finger_width = max(self.min_tx_width, self.size * self.min_tx_width / 2)
        finger_width = utils.round_to_grid(finger_width)
        self.tx_width = finger_width
        debug.info(3, "Finger width = %.3g", finger_width)

        self.tx = ptx(width=finger_width, mults=4, tx_type="nmos", contact_poly=True,
                      dummy_pos=[1, 2])
        self.add_mod(self.tx)

    def add_ptx_inst(self):
        gate_pin = self.tx.get_pins("G")[0]
        y_offset = max(0.5 * self.bus_width + self.tx.height, gate_pin.cy())
        x_offset = self.mid_x - 0.5 * self.tx.width
        debug.info(3, "tx x_offset = %.3g y_offset = %.3g", x_offset, y_offset)

        self.ptx_inst = self.add_inst("tx", self.tx, vector(x_offset, y_offset),
                                      mirror=MIRROR_X_AXIS)
        self.connect_inst([], check=False)

    def add_enables(self):
        gate_pins = self.get_sorted_pins("G")
        y_bottom = gate_pins[0].cy()
        y_top = y_bottom + self.bus_width + utils.round_to_grid(1.5 * self.bus_space)

        fill_width = m1m2.w_2
        _, fill_height = self.calculate_min_area_fill(fill_width, layer=METAL2)

        via_extension = (self.get_drc_by_layer(METAL3, "wide_metal_via_extension") or 0.0)

        y_offsets = [y_top, y_bottom]
        pin_names = ["bl_reset", "br_reset"]
        m2_top = None
        for i in range(2):
            self.add_layout_pin(pin_names[i], METAL3,
                                vector(0, y_offsets[i] - 0.5 * self.bus_width),
                                width=self.width, height=self.bus_width)
            pin_index = i * 2
            tx_pins = gate_pins[pin_index:pin_index + 2]
            mid_x = 0.5 * (tx_pins[0].cx() + tx_pins[-1].cx())
            offset = vector(mid_x, tx_pins[0].cy())

            height = max(poly_contact.h_2, m1m2.h_1)
            self.add_rect_center(METAL1, offset, height=height,
                                 width=tx_pins[-1].rx() - tx_pins[0].lx())
            bl_space = self.get_parallel_space(METAL2) + 0.5 * m1m2.w_2

            if i == 0:
                bitcell_pin = self.bitcell.get_pin("bl")
                m1m2_x = bitcell_pin.rx() + bl_space
                via_y = (y_bottom + 0.5 * self.bus_width + via_extension +
                         self.get_parallel_space(METAL3) + 0.5 * m1m2.w_2)
                self.add_cross_contact_center(cross_m2m3, vector(m1m2_x, via_y))
                self.add_rect(METAL2, vector(m1m2_x - 0.5 * self.m2_width, offset.y),
                              height=via_y - offset.y)
                m3_y = via_y - 0.5 * m2m3.w_2 - via_extension
                self.add_rect(METAL3, vector(m1m2_x - 0.5 * m2m3.h_2, m3_y),
                              width=m2m3.h_2, height=y_top - m3_y)
                m2_top = via_y + 0.5 * m2m3.h_1
            else:
                bitcell_pin = self.bitcell.get_pin("br")
                m1m2_x = bitcell_pin.lx() - bl_space
                self.add_cross_contact_center(cross_m2m3, vector(m1m2_x, y_offsets[i]))

            fill_bottom = offset.y - 0.5 * m1m2.h_2
            fill_top = min(fill_bottom + fill_height, m2_top)
            fill_bottom = fill_top - fill_height
            if fill_height > 0:
                self.add_rect(METAL2, vector(m1m2_x - 0.5 * m1m2.w_2, fill_bottom),
                              width=m1m2.w_2, height=fill_height)

            self.add_contact_center(m1m2.layer_stack, vector(m1m2_x, offset.y))

        self.m2_fill_top = m2_top

    def fill_drain_m1(self):
        self.fill_rects = fill_rects = []
        fill = calculate_tx_metal_fill(self.ptx_inst.mod.tx_width, self)
        if not fill:
            return

        self.drain_via_y = (self.m2_fill_top + self.get_line_end_space(METAL2) +
                            0.5 * m1m2.w_2)

        tx_pin = self.ptx_inst.get_pins("S")[0]
        fill_width = self.poly_pitch - self.get_parallel_space(METAL1)
        _, fill_height = self.calculate_min_area_fill(fill_width, layer=METAL1)
        fill_height = max(fill_height, tx_pin.height(),
                          self.drain_via_y + 0.5 * m1m2.h_1 - tx_pin.by())
        drain_pins = self.get_sorted_pins("D")
        for i in range(2):
            pin = drain_pins[i]
            offset = vector(pin.cx() - 0.5 * fill_width, pin.by())
            fill_rects.append(self.add_rect(METAL1, offset, width=fill_width,
                                            height=fill_height))

    def add_gnd_pins(self):
        source_pins = self.get_sorted_pins("S")

        m1_top = source_pins[0].uy()
        if self.fill_rects:
            m1_top = max(m1_top, self.fill_rects[0].uy())

        y_offset = m1_top + self.get_line_end_space(METAL1)
        height = max(self.rail_height, m2m3.h_1)
        m1_gnd = self.add_layout_pin("gnd", METAL1, vector(0, y_offset),
                                     width=self.width, height=height)
        self.m1_gnd = m1_gnd

        fill_width = self.poly_pitch - self.get_parallel_space(METAL1)

        for i in range(3):
            pin = source_pins[i]
            self.add_rect(METAL1, vector(pin.cx() - 0.5 * fill_width, pin.by()),
                          width=fill_width, height=m1_gnd.cy() - pin.by())
        self.height = m1_gnd.uy()

    def connect_bitlines(self):
        drain_pins = self.get_sorted_pins("D")
        pin_names = ["bl", "br"]

        for i in range(2):
            tx_pin = drain_pins[i]
            pin_name = pin_names[i]
            bitcell_pin = self.bitcell.get_pin(pin_name)
            via_offset = vector(tx_pin.cx(), self.drain_via_y)
            self.add_cross_contact_center(cross_m1m2, via_offset)
            offset = vector(bitcell_pin.cx(), via_offset.y - 0.5 * m1m2.w_2)
            self.add_rect(METAL2, offset, width=via_offset.x - offset.x,
                          height=m1m2.w_2)
            offset = vector(bitcell_pin.lx(), 0)
            self.add_layout_pin(pin_name, METAL2, offset, width=bitcell_pin.width(),
                                height=self.height)

    def connect_gnd_pins(self):
        pin = self.m1_gnd
        AnalogMixin.add_m1_m3_power_via(self, pin, add_m3_pin=True)
