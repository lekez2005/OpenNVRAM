from base import utils
from base.contact import cross_m2m3, cross_m1m2, m1m2, m2m3, m3m4
from base.design import METAL2, METAL3, ACTIVE, METAL1, METAL4
from base.vector import vector
from base.well_active_contacts import get_max_contact
from pgates.ptx import ptx
from pgates.ptx_spice import ptx_spice
from tech import parameter
from modules.cam.cam_precharge import CamPrecharge


class SotfetCamPrecharge(CamPrecharge):
    """Discharge only, no equalizer => Two finger nmos"""

    def __init__(self, name, size=1, has_precharge=True):
        super().__init__(name, size, has_precharge=False)

    def create_modules(self):
        """Create 2 finger nmos and pmos"""
        self.nmos_width = utils.round_to_grid(self.size * parameter["min_tx_size"])
        self.nmos = ptx(tx_type="nmos", width=self.nmos_width, connect_poly=True, mults=2)
        self.add_mod(self.nmos)

    def add_spice_connections(self):
        spice_obj = ptx_spice(tx_type="nmos", width=self.nmos_width, mults=1)
        for pin_name in ["bl", "br"]:
            self.add_inst(name=f"{pin_name}_nmos", mod=spice_obj,
                          offset=vector(0, 0))
            self.connect_inst([pin_name, "discharge", "gnd", "gnd"], check=False)

    def add_enable_pins(self):
        fill_height = cross_m2m3.height
        _, fill_width = self.calculate_min_area_fill(fill_height, layer=METAL2)
        gate_pin = self.nmos_inst.get_pin("G")
        self.add_layout_pin("discharge", METAL3,
                            offset=vector(0, gate_pin.cy() - 0.5 * self.bus_width),
                            width=self.width, height=self.bus_width)
        offset = vector(0.5 * self.width, gate_pin.cy())
        self.add_cross_contact_center(cross_m1m2, offset, rotate=True)
        self.add_cross_contact_center(cross_m2m3, offset)
        if fill_width:
            self.add_rect_center(METAL2, offset=offset,
                                 width=fill_width, height=fill_height)

    def setup_layout_constants(self):
        super().setup_layout_constants()
        bitcell_pin = self.bitcell.get_pin("bl")
        self.height -= (self.get_line_end_space(METAL2) + bitcell_pin.width())

    @staticmethod
    def get_bitline_drain_source_indices():
        return [0, 2]

    def add_bitlines(self):
        pin_names = ["bl", "br"]

        # add m1m2 contact
        active_rect = max(self.nmos.get_layer_shapes(ACTIVE), key=lambda x: x.height)
        cont_m1m2 = get_max_contact(layer_stack=m1m2.layer_stack, height=active_rect.height)
        cont_m2m3 = get_max_contact(layer_stack=m2m3.layer_stack, height=active_rect.height)
        source_pins = list(sorted(self.nmos_inst.get_pins("S"), key=lambda x: x.lx()))

        for i, pin_name in enumerate(pin_names):
            bitcell_pin = self.bitcell.get_pin(pin_name)
            x_offset = bitcell_pin.lx()
            precharge_pin = self.add_layout_pin(pin_name, METAL4,
                                                offset=vector(x_offset, 0),
                                                width=bitcell_pin.width(),
                                                height=self.height)
            tx_pin = source_pins[i]

            conts = []
            for cont in [cont_m1m2, cont_m2m3]:
                offset = vector(tx_pin.cx() - 0.5 * cont.width,
                                tx_pin.cy() - 0.5 * cont.height)
                conts.append(self.add_inst(cont.name, cont, offset))
                self.connect_inst([])

            self.fill_source_drain(pin_name, tx_pin, self.nmos_inst, conts[0], METAL1)
            self.fill_source_drain(pin_name, tx_pin, self.nmos_inst, conts[1], METAL2)
            self.fill_source_drain(pin_name, tx_pin, self.nmos_inst, conts[1], METAL3)

            cont_inst = conts[1]
            fill_height = m3m4.first_layer_height
            self.add_rect(METAL3,
                          offset=vector(precharge_pin.cx(), cont_inst.cy() - 0.5 * fill_height),
                          height=fill_height,
                          width=cont_inst.cx() - precharge_pin.cx())
            self.add_contact_center(m3m4.layer_stack, vector(precharge_pin.cx(), tx_pin.cy()))

    def connect_power(self):
        drain_pin = self.nmos_inst.get_pin("D")
        rail_height = self.get_rail_height()
        y_offsets = 0.5 * self.contact_implant_height - 0.5 * rail_height
        self.add_rect(METAL1, offset=vector(drain_pin.lx(), drain_pin.cy()),
                      width=drain_pin.width(), height=y_offsets - drain_pin.cy())
