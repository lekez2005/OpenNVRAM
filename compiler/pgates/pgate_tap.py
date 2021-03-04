from base import unique_meta, contact
from base.design import design, METAL1, PIMP, NIMP, PWELL, NWELL, ACTIVE
from base.vector import vector
from base.well_active_contacts import calculate_num_contacts
from pgates.pgate import pgate
from tech import drc, add_tech_layers


class pgate_tap(design, metaclass=unique_meta.Unique):

    @classmethod
    def get_name(cls, pgate_mod: pgate):
        name = "pgate_tap_{}".format(pgate_mod.name)
        return name

    def __init__(self, pgate_mod: pgate):
        design.__init__(self, self.name)
        self.pgate_mod = pgate_mod
        self.create_layout()

    def create_layout(self):
        self.height = self.pgate_mod.height
        self.add_contacts()
        self.add_boundary()
        add_tech_layers(self)

    def add_contacts(self):

        active_enclosure = self.implant_enclose_active
        dummy_to_active = 0
        if self.has_dummy:
            dummy_to_active = drc.get("parallel_dummy_to_active", self.poly_to_active)

        pgate_mod = self.pgate_mod
        pgate_active = pgate_mod.n_active_rect
        # calculate min m1 x
        m1_space = max(self.get_parallel_space(METAL1), self.get_line_end_space(METAL1))
        z_pin = self.pgate_mod.get_pin("Z")
        min_m1_x = (z_pin.rx() - pgate_mod.width + m1_space)
        # calculate based on active width
        tap_layers = [PIMP, NIMP]
        pgate_layers = [NIMP, PIMP]

        active_rects = []
        implant_y_offsets = []
        implant_x_offsets = []

        for i in range(2):
            pgate_implant = max(pgate_mod.get_layer_shapes(pgate_layers[i]),
                                key=lambda x: x.width * x.height)
            implant_x = max(0, pgate_implant.rx() - pgate_mod.width)
            active_x = max(implant_x + active_enclosure,
                           min_m1_x + 0.5 * contact.well.second_layer_width -
                           0.5 * contact.well.first_layer_width)
            if self.has_dummy:
                active_x = max(active_x, 0.5 * pgate_mod.poly_width + dummy_to_active)
            if i == 0:
                implant_top = pgate_implant.uy() - max(self.implant_space,
                                                       self.well_enclose_active)
                implant_bottom = - 0.5 * self.implant_width
                active_bottom = max(0, implant_bottom + active_enclosure)
                active_top = implant_top - active_enclosure
            else:
                implant_top = self.height + 0.5 * self.implant_width
                active_top = min(self.height, implant_top - active_enclosure)
                implant_bottom = pgate_implant.by() + max(self.implant_space,
                                                          self.well_enclose_active)
                active_bottom = implant_bottom + active_enclosure
            # add active
            active_height = active_top - active_bottom
            _, active_width = self.calculate_min_area_fill(active_height, layer=ACTIVE)
            active_width = max(self.active_width, active_width,
                               self.implant_width - 2 * active_enclosure)
            active_rect = self.add_rect(ACTIVE, offset=vector(active_x, active_bottom),
                                        width=active_width, height=active_height)
            # add contact
            sample_contact = calculate_num_contacts(self, active_height - self.contact_spacing,
                                                    return_sample=True)
            self.add_contact_center(sample_contact.layer_stack, offset=vector(active_rect.cx(),
                                                                              active_rect.cy()),
                                    size=sample_contact.dimensions)
            y_offset = 0 if i == 0 else self.height
            x_offset = active_rect.cx() - 0.5 * sample_contact.second_layer_width
            self.add_rect(METAL1, offset=vector(x_offset, y_offset),
                          height=active_rect.cy() - y_offset,
                          width=sample_contact.second_layer_width)

            active_rects.append(active_rect)
            implant_x_offsets.append(implant_x)
            implant_y_offsets.append((implant_bottom, implant_top))

        active_rect = max(active_rects, key=lambda x: x.rx())
        implant_rects = []

        for i in range(2):
            implant_x = implant_x_offsets[i]
            implant_bottom, implant_top = implant_y_offsets[i]

            implant_height = implant_top - implant_bottom
            _, implant_width = self.calculate_min_area_fill(implant_height, layer=tap_layers[i])
            implant_width = max(implant_width, self.implant_width,
                                active_rect.rx() + active_enclosure - implant_x)
            implant_rect = self.add_rect(tap_layers[i], vector(implant_x, implant_bottom),
                                         width=implant_width, height=implant_height)
            implant_rects.append(implant_rect)
            # wells
            if i == 0 and self.has_pwell:
                layer = PWELL
            elif i == 1:
                layer = NWELL
            else:
                layer = None
            if layer is not None:
                pgate_well_rect = pgate_mod.get_layer_shapes(layer)[0]

                def get_offset(func):
                    if func in ["rx", "uy"]:
                        sign, min_max = 1, max
                    else:
                        sign, min_max = -1, min
                    offset = min_max(getattr(implant_rect, func)(),
                                     getattr(active_rects[i], func)() +
                                     sign * self.well_enclose_active)
                    if func in ["uy", "by"]:
                        offset = min_max(offset, getattr(pgate_well_rect, func)())
                    return offset

                x_offset, y_offset = get_offset("lx"), get_offset("by")
                self.add_rect(layer, vector(x_offset, y_offset),
                              width=get_offset("rx") - x_offset,
                              height=get_offset("uy") - y_offset)

        implant_rect = max(implant_rects, key=lambda x: x.rx())

        active_space = self.get_space_by_width_and_length(ACTIVE, max_width=active_rect.height)

        pgate_implant = max(pgate_mod.get_layer_shapes(NIMP),
                            key=lambda x: x.width * x.height)

        self.width = max(active_rect.rx() + active_space - pgate_active.lx(),
                         implant_rect.rx() - min(0, - pgate_implant.lx()))
        if self.has_dummy:
            self.width = max(self.width, active_rect.rx() + dummy_to_active +
                             0.5 * pgate_mod.poly_width)
        for pin_name in ["vdd", "gnd"]:
            pin = pgate_mod.get_pin(pin_name)
            self.add_rect(pin.layer, offset=vector(0, pin.by()), height=pin.height(),
                          width=self.width)

    @staticmethod
    def wrap_pgate_tap(pgate_mod, tap_mod):

        class PgateAndTap(design, metaclass=unique_meta.Unique):

            @classmethod
            def get_name(cls):
                name = "pgate_and_tap_{}".format(pgate_mod.name)
                return name

            def __init__(self):
                super().__init__(self.name)
                self.add_mod(pgate_mod)
                self.pgate_inst = self.add_inst("pgate", pgate_mod, vector(0, 0))
                self.connect_inst(pgate_mod.pins)
                self.tap_inst = self.add_inst("tap", tap_mod, offset=self.pgate_inst.lr())
                self.connect_inst([])
                self.add_pin_list(pgate_mod.pins)
                for pin_name in pgate_mod.pins:
                    self.copy_layout_pin(self.pgate_inst, pin_name)
                self.width = self.tap_inst.rx()
                self.height = self.pgate_inst.uy()

        return PgateAndTap()
