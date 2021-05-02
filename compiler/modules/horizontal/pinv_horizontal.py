from base import unique_meta, contact, utils
from base.contact import m1m2
from base.design import METAL1, CONTACT, METAL2, POLY
from base.vector import vector
from modules.horizontal.pgate_horizontal import pgate_horizontal
from pgates.ptx_spice import ptx_spice
from tech import drc


class pinv_horizontal(pgate_horizontal, metaclass=unique_meta.Unique):
    """Inverters with horizontal orientation for use in
    push-rules restridted control buffers and pre-decoders"""
    all_nmos = True
    all_pmos = True

    @classmethod
    def get_name(cls, size=1, beta=None):
        beta, beta_suffix = cls.get_beta(beta, size)
        name = "pinv_horizontal_{:.3g}{}".format(size, beta_suffix).replace(".", "__")
        return name

    def create_layout(self):
        self.calculate_constraints()
        if self.num_instances > 1:
            self.instances_mod = pinv_horizontal(size=self.size / self.num_instances,
                                                 beta=self.beta)
            self.add_mod(self.instances_mod)
            self.add_pins()
            self.add_instances()
            return

        super().create_layout()

    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "Z", "vdd", "gnd"])

    def calculate_constraints(self):
        num_fingers = self.calculate_num_fingers(self.size)
        self.num_instances = 1

        while num_fingers is None and self.num_instances < 4:
            self.num_instances += 1
            num_fingers = self.calculate_num_fingers(self.size / self.num_instances)

        if num_fingers is None:
            # if still too large, bail
            if num_fingers is None:
                raise ValueError("Cannot estimate number of fingers to "
                                 "use. Size {} may be too large".format(self.size))
        self.num_fingers = num_fingers
        self.tx_mults = num_fingers

    def calculate_num_fingers(self, size):
        """Estimate the number of fingers
        Ranges from 1 to cls.tx_mults
        """
        tx_mults = self.max_tx_mults

        nmos_width = size * self.min_tx_width
        pmos_width = self.beta * size * self.min_tx_width

        finger_width = max(nmos_width, pmos_width) / tx_mults
        if finger_width > drc["maxwidth_tx"]:
            return None

        while tx_mults > 0:
            self.nmos_finger_width = nmos_finger_width = utils.floor(nmos_width / tx_mults)
            self.pmos_finger_width = pmos_finger_width = utils.floor(pmos_width / tx_mults)
            if nmos_finger_width < self.min_tx_width or pmos_finger_width < self.min_tx_width:
                tx_mults -= 1
            else:
                break
        return tx_mults

    def connect_inputs(self):

        contact_width = self.contact_width
        nmos_poly_offsets, pmos_poly_offsets, _ = self.get_poly_y_offsets(self.num_fingers)

        all_contact_mid_y = [x + 0.5 * self.poly_width for x in
                             nmos_poly_offsets + pmos_poly_offsets]

        x_offset = self.gate_contact_x + 0.5 * contact_width
        for y_offset in all_contact_mid_y:
            self.add_rect_center(CONTACT, offset=vector(x_offset, y_offset))
            poly_width = self.contact_width + 2 * contact.poly.first_layer_vertical_enclosure
            poly_height = self.contact_width + 2 * contact.poly.first_layer_horizontal_enclosure
            self.add_rect_center(POLY, offset=vector(x_offset, y_offset),
                                 width=poly_width, height=poly_height)

        m1_x_extension = 0.5 * contact.poly.second_layer_width
        m1_y_extension = 0.5 * contact.poly.second_layer_height

        pin_y = min(all_contact_mid_y) - m1_y_extension
        pin_height = max(all_contact_mid_y) - pin_y + m1_y_extension

        self.add_layout_pin("A", METAL1, offset=vector(x_offset - m1_x_extension, pin_y),
                            width=2 * m1_x_extension, height=pin_height)

    def get_ptx_connections(self):
        return [
            (self.pmos, ["Z", "A", "vdd", "vdd"]),
            (self.nmos, ["Z", "A", "gnd", "gnd"])
        ]

    def add_instances(self):
        offset = vector(0, 0)
        self.instances = []
        # add instances
        for i in range(self.num_instances):
            self.instances.append(self.add_inst("inv{}".format(i), mod=self.instances_mod,
                                                offset=offset))
            self.connect_inst(self.pins)
            offset = self.instances[-1].lr()

        self.width = self.instances[-1].rx()
        self.height = self.instances[-1].height

        # copy pins
        self.copy_layout_pin(self.instances[0], "A")
        self.copy_layout_pin(self.instances[-1], "Z")
        for pin_name in ["vdd", "gnd"]:
            pin = self.instances[0].get_pin(pin_name)
            self.add_layout_pin(pin_name, pin.layer, offset=pin.ll(),
                                height=pin.height(), width=self.width)

        # connect A and Z pins

        y_space = 1.5 * self.get_parallel_space(METAL2)
        connection_height = 1.5 * self.m2_width

        y_offsets = [self.instances_mod.mid_y + 0.5 * y_space,
                     self.instances_mod.mid_y - 0.5 * y_space - connection_height]
        via_offsets = [y_offsets[0], y_offsets[1] + connection_height - m1m2.height]
        pin_names = ["A", "Z"]
        for i in range(2):
            for j in range(self.num_instances):
                pin = self.instances[j].get_pin(pin_names[i])
                via_x = pin.cx() - 0.5 * m1m2.width
                self.add_contact(m1m2.layer_stack, offset=vector(via_x, via_offsets[i]))
            left_pin = self.instances[0].get_pin(pin_names[i])
            right_pin = self.instances[-1].get_pin(pin_names[i])
            self.add_rect(METAL2, offset=vector(left_pin.cx(), y_offsets[i]),
                          width=right_pin.cx() - left_pin.cx(), height=connection_height)
