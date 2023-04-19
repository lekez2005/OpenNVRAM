from base.analog_cell_mixin import AnalogMixin
from base.contact import cross_m1m2, cross_m2m3, m1m2, m2m3, m3m4
from base.design import PIMP, METAL1, METAL3, METAL2, ACTIVE, NWELL, METAL4
from base.utils import round_to_grid as rg
from base.vector import vector
from globals import OPTS
from modules.mram.sotfet.sotfet_mram_precharge_array import sotfet_mram_precharge_array
from modules.precharge import precharge
from pgates.ptx import ptx
from pgates.ptx_spice import ptx_spice
from tech import add_tech_layers


class PrechargeBlBr(precharge):

    def create_layout(self):
        self.bitcell = self.create_mod_from_str(OPTS.write_driver)
        self.set_layout_constants()
        self.add_transistor()
        self.connect_input_gates()
        self.connect_bitlines()
        self.add_nwell_contacts()
        self.add_bitlines()
        add_tech_layers(self)
        self.add_boundary()
        self.add_ptx_inst()

    @staticmethod
    def get_tx_mults():
        return 4

    def add_transistor(self):
        finger_width = max(self.ptx_width / 2, self.min_tx_width)
        tx = ptx(width=finger_width, mults=4, tx_type="pmos", contact_poly=True,
                 dummy_pos=[1, 2])
        self.add_mod(tx)

        y_offset = -tx.get_max_shape(PIMP, "by").by()

        offset = vector(self.mid_x - 0.5 * tx.width, y_offset)
        self.tx_inst = self.add_inst("tx", mod=tx, offset=offset)
        self.connect_inst([], check=False)

    def connect_input_gates(self):
        gate_pins = AnalogMixin.get_sorted_pins(self.tx_inst, "G")
        offset = gate_pins[0].center() - vector(0, 0.5 * self.m1_width)
        self.add_rect(METAL1, offset, height=self.m1_width,
                      width=gate_pins[-1].cx() - offset.x)
        offset = vector(self.mid_x, gate_pins[0].cy())
        self.add_cross_contact_center(cross_m1m2, offset, rotate=True)
        self.add_cross_contact_center(cross_m2m3, offset, rotate=False)
        self.add_layout_pin_center_rect("en", METAL3, offset=offset, width=self.width,
                                        height=self.bus_width)
        fill_height = cross_m2m3.h_1
        _, fill_width = self.calculate_min_area_fill(fill_height, layer=METAL2)
        self.add_rect_center(METAL2, offset, width=fill_width, height=fill_height)

    def connect_bitlines(self):
        drain_pins = AnalogMixin.get_sorted_pins(self.tx_inst, "D")
        m2_fill_height = cross_m2m3.h_1
        _, m2_fill_width = self.calculate_min_area_fill(m2_fill_height, layer=METAL2)

        active_tx = self.tx_inst.get_max_shape(ACTIVE, "by")
        mid_y = max(drain_pins[0].cy(), active_tx.by() + 0.5 * m2_fill_height)

        _, m1_fill_height = self.calculate_min_area_fill(drain_pins[0].width(),
                                                         layer=METAL1)
        if rg(m1_fill_height) > rg(drain_pins[0].height()):
            m1_fill_width = self.poly_pitch - self.get_parallel_space(METAL1)
            _, m1_fill_height = self.calculate_min_area_fill(m1_fill_width, layer=METAL1)
            m1_fill_y = min(active_tx.cy() - 0.5 * m1m2.h_1, drain_pins[0].by())
            m1_fill_height = max(m1_fill_height, drain_pins[0].uy() - m1_fill_y)
            self.m1_fill_top = m1_fill_y + m1_fill_height
        else:
            m1_fill_y = m1_fill_width = None
            self.m1_fill_top = drain_pins[0].uy()

        for i in range(2):
            pin_name = ["bl", "br"][i]
            bitcell_pin = self.bitcell.get_pin(pin_name)
            tx_pin = drain_pins[i]

            offset = vector(tx_pin.cx(), mid_y)
            # fill m1
            if m1_fill_y is not None:
                self.add_rect(METAL1, vector(tx_pin.cx() - 0.5 * m1_fill_width, m1_fill_y),
                              width=m1_fill_width, height=m1_fill_height)
            # fill m2
            self.add_rect_center(METAL2, offset=offset, width=m2_fill_width,
                                 height=m2_fill_height)
            # add vias
            self.add_contact_center(m1m2.layer_stack, offset=offset)
            self.add_cross_contact_center(cross_m2m3, offset=offset)
            # add m3 from drain to bitline pin
            m2_m3_ext = 0.5 * m2m3.h_2

            m3_via_x = bitcell_pin.cx()

            if i == 0:
                m3_x = m3_via_x - 0.5 * m3m4.w_1
                m3_fill_width = offset.x + m2_m3_ext - m3_x
            else:
                m3_x = offset.x - m2_m3_ext
                m3_fill_width = m3_via_x + 0.5 * m3m4.w_1 - m3_x

            self.add_contact_center(m3m4.layer_stack, vector(m3_via_x, offset.y))

            _, m3_fill_height = self.calculate_min_area_fill(m3_fill_width, layer=METAL3)
            m3_fill_height = max(m3_fill_height, self.m3_width)
            self.add_rect(METAL3, vector(m3_x, offset.y - 0.5 * m3_fill_height),
                          width=m3_fill_width, height=m3_fill_height)

        self.m2_fill_top = mid_y + 0.5 * m2_fill_height

    def add_bitlines(self):
        for i in range(2):
            pin_name = ["bl", "br"][i]
            bitcell_pin = self.bitcell.get_pin(pin_name)
            self.add_layout_pin(pin_name, METAL4, vector(bitcell_pin.lx(), 0),
                                width=bitcell_pin.width(), height=self.height)

    def add_nwell_contacts(self):
        # based on metal
        active_tx = self.tx_inst.get_max_shape(ACTIVE, "uy")
        m1_fill_top = max(self.m1_fill_top, active_tx.uy())
        mid_y = m1_fill_top + self.get_parallel_space(METAL1) + 0.5 * self.rail_height
        mid_y = max(mid_y, self.m2_fill_top + self.get_parallel_space(METAL2) +
                    0.5 * self.rail_height)
        # add m1, m3 pins
        m1_pin = self.add_layout_pin("vdd", METAL1, vector(0, mid_y - 0.5 * self.rail_height),
                                     width=self.width, height=self.rail_height)
        AnalogMixin.add_m1_m3_power_via(self, m1_pin)

        self.height = mid_y + 0.5 * self.rail_height
        # connect source pins to vdd
        fill_width = self.poly_pitch - self.get_parallel_space(METAL1)
        for pin in self.tx_inst.get_pins("S"):
            self.add_rect(METAL1, vector(pin.cx() - 0.5 * fill_width, pin.by()),
                          width=fill_width, height=mid_y - pin.by())
        # extend nwell to top
        nwell = self.get_max_shape(NWELL, "uy", recursive=True)
        self.add_rect(NWELL, nwell.ll(), width=nwell.width, height=self.height - nwell.by())

    def add_ptx_inst(self):
        finger_width = self.tx_inst.mod.tx_width
        self.pmos = ptx_spice(tx_type="pmos", width=finger_width, mults=2)
        self.add_inst(name="bl_pmos", mod=self.pmos, offset=vector(0, 0))
        self.connect_inst(["bl", "en", "vdd", "vdd"])
        self.add_inst(name="br_pmos", mod=self.pmos, offset=vector(0, 0))
        self.connect_inst(["br", "en", "vdd", "vdd"])


class PrechargeBlBrArray(sotfet_mram_precharge_array):
    def create_layout(self):
        super().create_layout()
        self.add_dummy_poly(self.pc_cell, self.child_insts, words_per_row=1)
