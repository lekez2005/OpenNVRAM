from base import utils, contact
from base.contact import m1m2
from base.design import design, PO_DUMMY, NIMP, PIMP, ACTIVE, METAL1, NWELL
from base.hierarchy_layout import GDS_ROT_270
from base.unique_meta import Unique
from base.vector import vector
from modules.push_rules.push_bitcell_array import push_bitcell_array
from modules.horizontal.wordline_buffer import wordline_buffer
from modules.horizontal.wordline_inverter import wordline_inverter
from tech import drc
import tech


class buffer_tap(design, metaclass=Unique):
    rotation_for_drc = GDS_ROT_270

    @classmethod
    def get_name(cls, _):
        return "wordline_buffer_tap"

    def __init__(self, buffer: wordline_buffer):
        super().__init__(self.name)
        self.buffer = buffer
        self.create_layout()
        self.add_nwell()
        if hasattr(tech, "add_tech_layers"):
            tech.add_tech_layers(self)

    def create_layout(self):
        self.width = self.buffer.width
        self.height = push_bitcell_array.body_tap.height

        wordline_buffer_array.create_dummies(self, self.buffer,
                                             top_y=0, bottom_y=self.height)

        inverter = self.buffer.buffer_invs[-1]  # type: wordline_inverter

        nimplant = inverter.get_layer_shapes(NIMP)[0]
        implant_bottom = nimplant.height - inverter.height
        implant_top = self.height - implant_bottom
        implant_height = implant_top - implant_bottom
        implant_width = utils.ceil(drc["minarea_implant"] / implant_height)

        mid_y = 0.5 * self.height

        if inverter.insert_poly_dummies:
            dummy_rects = self.get_layer_shapes(PO_DUMMY, PO_DUMMY)
            dummy_top = min(map(lambda x: x.by(),
                                filter(lambda x: x.cy() > mid_y, dummy_rects)))
            dummy_bottom = max(map(lambda x: x.uy(),
                                   filter(lambda x: x.cy() < mid_y, dummy_rects)))
            active_space = drc["poly_dummy_to_active"]
            active_top = dummy_top - active_space
            active_bottom = dummy_bottom + active_space
        else:
            active_bottom = implant_bottom + self.implant_enclose_active
            active_top = implant_top - self.implant_enclose_active
        active_height = active_top - active_bottom
        active_width = utils.ceil(drc["minarea_cont_active_thin"] / active_height)

        implant_width = max(implant_width, active_width + 2 * self.implant_enclose_active)
        # expect nimplant to be smaller than pimplant so use for minimum implant
        implant_width = max(implant_width, nimplant.width - 2 * self.implant_space)

        active_width = implant_width - 2 * self.implant_enclose_active

        # use just the rightmost inverter, assumes decoder and has tap for leftmost psub
        inverter_inst = self.buffer.module_insts[-1]
        inverter = inverter_inst.mod
        x_shift = inverter_inst.lx()

        pimplant = inverter.get_layer_shapes(PIMP)[0]

        x_offsets = [x_shift + pimplant.lx(), x_shift + pimplant.rx() + self.implant_space]
        layers = [NIMP, PIMP]
        num_contacts = self.calculate_num_contacts(max(active_width, active_height))

        for i in range(2):
            # add implant
            self.add_rect(layers[i], offset=vector(x_offsets[i], implant_bottom),
                          width=implant_width, height=implant_height)
            # add active
            mid_x = x_offsets[i] + 0.5 * implant_width
            self.add_rect_center(ACTIVE, offset=vector(mid_x, mid_y),
                                 width=active_width, height=active_height)
            # add contacts
            if active_width > active_height:
                rotate = 90
            else:
                rotate = 0
            self.add_contact_center(contact.well.layer_stack, offset=vector(mid_x, mid_y),
                                    size=[1, num_contacts], rotate=rotate)
            # extend to rails
            destination_y = (i % 2 == 0) * self.height
            rect_y = 0.5 * (destination_y + mid_y)
            self.add_rect_center(METAL1, offset=vector(mid_x, rect_y),
                                 width=m1m2.height, height=destination_y - mid_y)
        self.add_boundary()

    def add_nwell(self):
        left_nwell = self.buffer.buffer_invs[0].get_layer_shapes(NWELL)[0]
        right_nwell = self.buffer.buffer_invs[1].get_layer_shapes(NWELL)[0]
        left_x = left_nwell.lx()
        right_x = right_nwell.rx() + self.buffer.module_insts[1].lx()
        self.add_rect(NWELL, offset=vector(left_x, 0), width=right_x - left_x,
                      height=self.height)


class wordline_buffer_array(design):
    rotation_for_drc = GDS_ROT_270

    def __init__(self, rows, buffer_stages):
        super().__init__("wordline_buffer_array")
        self.rows = rows
        self.buffer_stages = buffer_stages
        self.buffer_insts = []
        self.add_pins()
        self.create_layout()
        self.add_layout_pins()
        self.add_boundary()

    @staticmethod
    def create_dummies(parent_mod: design, buffer: wordline_buffer, top_y, bottom_y):
        inverter = buffer.buffer_invs[0]
        if not inverter.insert_poly_dummies:
            return
        y_offsets = [top_y - 0.5 * parent_mod.poly_space - inverter.poly_width,
                     bottom_y + 0.5 * parent_mod.poly_space]
        dummy_enclosure = 0.5 * parent_mod.poly_to_field_poly
        for i in range(2):
            direction = 1 if i == 0 else -1
            for j in [1, 2]:
                y_offset = y_offsets[i] + direction * j * buffer.buffer_invs[0].poly_pitch
                parent_mod.add_rect(PO_DUMMY, offset=vector(dummy_enclosure, y_offset),
                                    width=parent_mod.width - 2 * dummy_enclosure,
                                    height=inverter.poly_width)

    def add_pins(self):
        self.add_pin_list(["decode[{}]".format(x) for x in range(self.rows)])
        self.add_pin_list(["wl[{}]".format(x) for x in range(self.rows)])
        self.add_pin_list(["vdd", "gnd"])

    def create_layout(self):
        self.create_modules()
        self.add_modules()
        self.create_dummies(self, self.buffer, top_y=self.buffer_insts[-1].uy(),
                            bottom_y=self.buffer_insts[0].by())

    def create_modules(self):
        self.buffer = wordline_buffer(buffer_stages=self.buffer_stages)
        self.add_mod(self.buffer)

        self.tap = buffer_tap(self.buffer)

        self.bitcell_offsets, self.tap_offsets, _ = push_bitcell_array. \
            get_bitcell_offsets(self.rows, 2)

        self.width = self.buffer.width
        self.height = self.bitcell_offsets[-1] + 2 * self.buffer.height

    def add_modules(self):

        for i in range(self.rows):
            y_offset = self.bitcell_offsets[i]
            if i % 2 == 0:
                mirror = "MX"
                y_offset += self.buffer.height
            else:
                mirror = ""

            offset = vector(0, y_offset)
            buffer_inst = self.add_inst("driver{}".format(i), self.buffer, offset=offset,
                                        mirror=mirror)
            self.connect_inst(["decode[{}]".format(i), "wl_bar[{}]".format(i),
                               "wl[{}]".format(i), "vdd", "gnd"])
            self.buffer_insts.append(buffer_inst)
        self.tap_insts = []
        for y_offset in self.tap_offsets:
            self.tap_insts.append(self.add_inst(self.tap.name, self.tap, offset=vector(0, y_offset)))
            self.connect_inst([])

    def add_layout_pins(self):
        for pin_name in ["vdd", "gnd"]:
            for i in range(self.rows):
                self.copy_layout_pin(self.buffer_insts[i], pin_name)
        for i in range(self.rows):
            self.copy_layout_pin(self.buffer_insts[i], "in", "decode[{}]".format(i))
            self.copy_layout_pin(self.buffer_insts[i], "out", "wl[{}]".format(i))
