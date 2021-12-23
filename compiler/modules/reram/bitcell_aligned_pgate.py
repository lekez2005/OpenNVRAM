from abc import ABC

import tech
from base import utils
from base.contact import well as well_contact, poly as poly_contact, cross_poly, m1m2, m2m3, cross_m1m2, cross_m2m3
from base.design import design, ACTIVE, METAL1, POLY, METAL3, METAL2
from base.layout_clearances import find_clearances, HORIZONTAL
from base.vector import vector
from base.well_active_contacts import calculate_num_contacts
from globals import OPTS
from pgates.ptx import ptx
from pgates.ptx_spice import ptx_spice


class BitcellAlignedPgate(design, ABC):
    mod_name = None

    def create_layout(self):
        raise NotImplemented

    def __init__(self, size, name=None):
        name = name or f"{self.mod_name}_{size:.4g}"
        self.size = size
        design.__init__(self, name)
        self.create_layout()

    @staticmethod
    def get_sorted_pins(tx_inst, pin_name):
        return list(sorted(tx_inst.get_pins(pin_name), key=lambda x: x.lx()))

    def create_ptx(self, size, is_pmos=False, **kwargs):
        width = size * tech.spice["minwidth_tx"]
        if is_pmos:
            tx_type = "pmos"
            width *= tech.parameter["beta"]
        else:
            tx_type = "nmos"
        tx = ptx(width=width, tx_type=tx_type, **kwargs)
        self.add_mod(tx)
        return tx

    def create_ptx_spice(self, tx: ptx, mults=1, scale=1):
        tx_spice = ptx_spice(width=tx.tx_width * scale, mults=mults,
                             tx_type=tx.tx_type, tx_length=tx.tx_length)
        self.add_mod(tx_spice)
        return tx_spice

    def flatten_tx(self, *args):
        for tx_inst in args:
            ptx.flatten_tx_inst(self, tx_inst)

    def create_modules(self):
        self.bitcell = self.create_mod_from_str(OPTS.bitcell)
        self.width = self.bitcell.width
        self.mid_x = 0.5 * self.width

    def calculate_bottom_space(self):
        well_contact_mid_y = 0.5 * self.rail_height
        well_contact_active_top = well_contact_mid_y + 0.5 * well_contact.first_layer_width
        return well_contact_active_top + self.get_space(ACTIVE)

    def add_mid_poly_via(self, nmos_poly, mid_y, min_via_x=None):
        horz_poly = poly_contact.first_layer_width > nmos_poly[0].width()
        x_offsets = []

        for i in [1, 2]:
            # add poly contact
            if horz_poly:
                x_offset = min_via_x or nmos_poly[i].cx()
            else:
                x_offset = nmos_poly[i].cx()
            x_offsets.append(x_offset)

            if horz_poly and i == 1:
                self.add_cross_contact_center(cross_poly, vector(x_offset, mid_y))
            elif not horz_poly:
                self.add_contact_center(poly_contact.layer_stack, vector(x_offset, mid_y))

        # horizontal join poly contact
        layer = POLY if horz_poly else METAL1
        height = (poly_contact.first_layer_height
                  if horz_poly else poly_contact.second_layer_height)
        self.add_rect(layer, vector(x_offset, mid_y - 0.5 * height),
                      height=height, width=nmos_poly[2].cx() - x_offset)

        return x_offsets[0]

    def add_power_tap(self, y_offset, pin_name, tx_inst, add_m3=True):
        if pin_name == "vdd":
            well_type = "nwell"
        else:
            well_type = "pwell"
        implant_type = well_type[0]

        max_width = self.width - self.get_space(ACTIVE)
        num_contacts = calculate_num_contacts(self, max_width,
                                              layer_stack=well_contact.layer_stack,
                                              return_sample=False)
        pin_width = self.width
        if add_m3:
            pin_width += max(m1m2.first_layer_height, m2m3.second_layer_height)
        x_offset = 0.5 * (self.width - pin_width)
        pin = self.add_layout_pin(pin_name, METAL1, offset=vector(x_offset, y_offset),
                                  height=self.rail_height, width=pin_width)
        cont = self.add_contact_center(well_contact.layer_stack, pin.center(), rotate=90,
                                       size=[1, num_contacts],
                                       implant_type=implant_type,
                                       well_type=well_type)

        # add well
        if tech.info[f"has_{well_type}"]:
            well_width = cont.mod.first_layer_height + 2 * self.well_enclose_active
            well_width = max(self.width, well_width)
            x_offset = 0.5 * (self.width - well_width)
            ptx_rects = tx_inst.get_layer_shapes(well_type)
            ptx_rect = max(ptx_rects, key=lambda x: x.width * x.height)

            if pin.cy() < tx_inst.cy():
                well_top = ptx_rect.uy()
                well_bottom = (pin.cy() - 0.5 * well_contact.first_layer_width -
                               self.well_enclose_active)
            else:
                well_top = (pin.cy() + 0.5 * well_contact.first_layer_width +
                            self.well_enclose_active)
                well_bottom = ptx_rect.by()
            self.add_rect(well_type, vector(x_offset, well_bottom), width=well_width,
                          height=well_top - well_bottom)

        if not add_m3:
            return pin, cont, well_type

        self.add_layout_pin(pin.name, METAL3, pin.ll(), width=pin.width(),
                            height=pin.height())
        open_spaces = find_clearances(self, layer=METAL2, direction=HORIZONTAL,
                                      region=(pin.by(), pin.uy()))

        min_space = (max(m1m2.second_layer_width, m2m3.first_layer_width) +
                     2 * self.get_parallel_space(METAL2))

        for space in open_spaces:
            space = [utils.round_to_grid(x) for x in space]
            if space[0] == 0.0:
                mid_contact = 0
            elif space[1] == self.width:
                mid_contact = self.width
            else:
                if space[1] - space[0] <= min_space:
                    continue
                mid_contact = utils.round_to_grid(0.5 * (space[0] + space[1]))
            offset = vector(mid_contact, pin.cy())
            self.add_cross_contact_center(cross_m1m2, offset, rotate=True)
            self.add_cross_contact_center(cross_m2m3, offset, rotate=False)

        return pin, cont, well_type

    def route_pin_to_power(self, pin_name, pin):
        power_pins = self.get_pins(pin_name)
        power_pin = min(power_pins, key=lambda x: abs(x.cy() - pin.cy()))
        self.add_rect(METAL1, vector(pin.lx(), pin.cy()), width=pin.width(),
                      height=power_pin.cy() - pin.cy())

    @staticmethod
    def calculate_active_to_poly_cont_mid(tx_type):
        """Distance from edge of active to middle of poly contact"""
        active_to_poly_contact = tech.drc.get(f"poly_contact_to_{tx_type[0]}_active",
                                              tech.drc["poly_contact_to_active"])
        return active_to_poly_contact + 0.5 * poly_contact.contact_width
