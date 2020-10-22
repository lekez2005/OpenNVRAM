from base import utils, contact
from base.contact import cross_contact, m2m3, m1m2, cross_m2m3
from base.design import METAL2, PIMP, NIMP, NWELL, METAL3, METAL1
from base.vector import vector
from modules.hierarchical_decoder import hierarchical_decoder
from pgates.pinv import pinv
from pgates.pnand2 import pnand2
from pgates.pnand3 import pnand3
from tech import drc


class stacked_hierarchical_decoder(hierarchical_decoder):

    def create_layout(self):
        super().create_layout()
        self.width = self.width - self.power_rail_x
        self.predecoder_width -= self.power_rail_x
        self.row_decoder_width = max(self.inv_inst[0].rx() - self.inv_inst[1].lx(),
                                     self.inv_inst[1].rx() - self.inv_inst[0].lx())
        self.translate_all(vector(self.power_rail_x, 0))

    def setup_layout_constants(self):
        super().setup_layout_constants()

        self.row_decoder_height = 0.5 * self.inv.height * self.rows
        self.height = self.predecoder_height + self.row_decoder_height

        # map row to predec groups
        row_index = 0
        self.row_to_predec = [None] * self.rows
        index_c_s = [-1] if len(self.predec_groups) == 2 else self.predec_groups[2]
        for index_c in index_c_s:
            for index_b in self.predec_groups[1]:
                for index_a in self.predec_groups[0]:
                    self.row_to_predec[row_index] = (index_a, index_b, index_c)
                    row_index += 1

    def create_vertical_rail(self):
        super().create_vertical_rail()

        # determine if row is left or right
        # place adjacent rows to left or right based on expected predecoder input position
        self.row_to_side = [""] * self.rows
        for row in range(0, self.rows, 2):
            row_a = self.row_to_predec[row][0]
            next_row_a = self.row_to_predec[row + 1][0]
            if self.rail_x_offsets[row_a] >= self.rail_x_offsets[next_row_a]:
                self.row_to_side[row] = "right"
                self.row_to_side[row + 1] = "left"
            else:
                self.row_to_side[row] = "left"
                self.row_to_side[row + 1] = "right"

    def add_modules(self):
        args = {
            "height": 2 * self.bitcell_height,
            "align_bitcell": True,
            "contact_nwell": False,
            "contact_pwell": False
        }
        self.inv = pinv(**args)
        self.add_mod(self.inv)
        self.nand2 = pnand2(**args)
        self.add_mod(self.nand2)
        self.nand3 = pnand3(**args)
        self.add_mod(self.nand3)

        self.create_predecoders()

    def add_row_arrays(self, mod, x_offsets, name_template):
        mirrors = ["XY", "MX", "MY", "R0"]
        instances = []

        left_x, right_x = x_offsets

        for row in range(self.rows):
            name = name_template.format(row)
            x_offset = left_x if self.row_to_side[row] == "left" else right_x
            y_index = int(row / 2)
            if y_index % 2 == 0:
                y_offset = self.predecoder_height + mod.height * (y_index + 1)
                if self.row_to_side[row] == "left":
                    mirror_index = 0
                else:
                    mirror_index = 1
            else:
                y_offset = self.predecoder_height + mod.height * y_index
                if self.row_to_side[row] == "left":
                    mirror_index = 2
                else:
                    mirror_index = 3

            instance = self.add_inst(name=name, mod=mod,
                                     offset=vector(x_offset, y_offset),
                                     mirror=mirrors[mirror_index])
            instances.append(instance)

        return instances

    def add_nand_array(self, nand_mod, correct=0):
        x_offsets = [- self.get_parallel_space(METAL2),
                     self.routing_width]

        self.nand_inst = self.add_row_arrays(nand_mod, x_offsets, "DEC_NAND[{0}]")

    def add_decoder_inv_array(self):
        if self.row_to_side[0] == "left":
            x_indices = [0, 1]
        else:
            x_indices = [1, 0]
        x_offsets = [self.nand_inst[x_indices[0]].lx(), self.nand_inst[x_indices[1]].rx()]
        self.inv_inst = self.add_row_arrays(self.inv, x_offsets, "DEC_INV_[{0}]")

        for row in range(self.rows):
            self.connect_inst(args=["Z[{0}]".format(row),
                                    "decode[{0}]".format(row),
                                    "vdd", "gnd"],
                              check=False)

    def route_decoder(self):
        for row in range(self.rows):
            # route nand output to output inv input
            if self.row_to_side[row] == "left":
                zr_pos = self.nand_inst[row].get_pin("Z").lc()
                al_pos = self.inv_inst[row].get_pin("A").rc()
            else:
                zr_pos = self.nand_inst[row].get_pin("Z").rc()
                al_pos = self.inv_inst[row].get_pin("A").lc()
            # ensure the bend is in the middle
            mid1_pos = vector(0.5 * (zr_pos.x + al_pos.x), zr_pos.y)
            mid2_pos = vector(0.5 * (zr_pos.x + al_pos.x), al_pos.y)
            self.add_path("metal1", [zr_pos, mid1_pos, mid2_pos, al_pos])

            z_pin = self.inv_inst[row].get_pin("Z")
            self.add_layout_pin(text="decode[{0}]".format(row),
                                layer="metal1",
                                offset=z_pin.ll(),
                                width=z_pin.width(),
                                height=z_pin.height())

    def add_body_contacts(self):
        implant_enclosure = drc["ptx_implant_enclosure_active"]
        implant_height = drc["minwidth_implant"]
        nwell_height = implant_height + 2 * self.well_enclose_implant

        if self.row_to_side[0] == "left":
            left_inst, right_inst = self.nand_inst[:2]
        else:
            left_inst, right_inst = reversed(self.nand_inst[:2])

        available_width = right_inst.lx() - left_inst.rx()
        active_width = available_width - 2 * implant_enclosure
        num_contacts = self.calculate_num_contacts(active_width)
        implant_width = nwell_width = available_width
        mid_x = 0.5 * (right_inst.lx() + left_inst.rx())

        for row in range(0, self.rows, 2):
            gnd_pin = self.nand_inst[row].get_pin("gnd")
            self.add_contact_center(contact.contact.active_layers,
                                    offset=vector(mid_x, gnd_pin.cy()), size=[num_contacts, 1])
            self.add_rect_center(PIMP, offset=vector(mid_x, gnd_pin.cy()),
                                 width=implant_width, height=implant_height)

            vdd_pin = self.nand_inst[row].get_pin("vdd")
            self.add_contact_center(contact.contact.active_layers,
                                    offset=vector(mid_x, vdd_pin.cy()), size=[num_contacts, 1])
            self.add_rect_center(NIMP, offset=vector(mid_x, vdd_pin.cy()),
                                 width=implant_width, height=implant_height)
            self.add_rect_center(NWELL, offset=(mid_x, vdd_pin.cy()),
                                 width=nwell_width, height=nwell_height)

        # add pimplant for top predecoder
        top_predecoder = max(self.pre2x4_inst + self.pre3x8_inst, key=lambda x: x.uy())
        predec_module = top_predecoder.mod
        pre_module_width = predec_module.inv_inst[0].width + predec_module.nand_inst[0].width
        vdd_pin = right_inst.get_pin("vdd")
        self.add_rect(PIMP, offset=vector(vdd_pin.lx(), vdd_pin.cy() - 0.5 * implant_height),
                      height=implant_height, width=pre_module_width)

    def connect_rails_to_decoder(self):
        self.add_mod(cross_m2m3)

        for row in range(0, self.rows, 2):
            if self.row_to_side[row] == "left":
                left_index = row
                right_index = row + 1
            else:
                left_index = row + 1
                right_index = row
            left_inst = self.nand_inst[left_index]
            right_inst = self.nand_inst[right_index]

            # right inst
            pins = ["A", "B", "C"]
            for i in range(len(self.predec_groups)):
                dest_pin = right_inst.get_pin(pins[i])
                left_pin = left_inst.get_pin(pins[i])
                predecoder_rail = self.rail_x_offsets[self.row_to_predec[right_index][i]]
                pin_bottom = dest_pin.cy() - 0.5 * right_inst.mod.gate_fill_height
                if i == 0:
                    # add to the right
                    via_y = pin_bottom - 0.5 * m1m2.height
                    self.add_contact_center(m1m2.layer_stack, offset=vector(predecoder_rail, via_y))
                    rect_x = predecoder_rail - 0.5 * m1m2.width
                    self.add_rect(METAL1, offset=vector(rect_x, pin_bottom),
                                  width=dest_pin.lx() - rect_x)
                    # add to the left
                    predecoder_rail = self.rail_x_offsets[self.row_to_predec[left_index][i]]
                    pin_top = 0.5 * left_inst.mod.gate_fill_height + left_pin.cy()
                    via_y = pin_top + 0.5 * m1m2.height
                    self.add_contact_center(m1m2.layer_stack, offset=vector(predecoder_rail, via_y))
                    rect_x = predecoder_rail + 0.5 * m1m2.width
                    self.add_rect(METAL1, offset=vector(left_pin.rx(), pin_top - self.m1_width),
                                  width=rect_x - left_pin.rx())

                elif i == 1:  # both left and right have the same rail
                    via_y = dest_pin.cy() - 0.5 * cross_m2m3.height
                    via_x = predecoder_rail - 0.5 * cross_m2m3.contact_width
                    self.add_inst(cross_m2m3.name, cross_m2m3, offset=vector(via_x, via_y))
                    self.add_rect(METAL3, offset=vector(left_pin.cx(), dest_pin.cy() - 0.5 * self.m3_width),
                                  width=dest_pin.cx() - left_pin.cx())
                    self.connect_inst([])
                    for pin in [left_pin, dest_pin]:
                        self.add_contact_center(m1m2.layer_stack, offset=pin.center())
                        self.add_contact_center(m2m3.layer_stack, offset=pin.center())
                        self.add_rect_center(METAL2, offset=pin.center(), height=left_inst.mod.gate_fill_height,
                                             width=left_inst.mod.gate_fill_width)
                elif i == 2:
                    via_y = (dest_pin.cy() + 0.5 * m2m3.height + self.get_line_end_space(METAL3) +
                             0.5 * m2m3.contact_width)
                    self.add_contact_center(m2m3.layer_stack, offset=vector(predecoder_rail, via_y))
                    self.add_rect(METAL3, offset=vector(left_pin.cx(), via_y - 0.5 * self.m3_width),
                                  width=dest_pin.cx() - left_pin.cx())
                    pins = [left_pin, dest_pin]
                    for j in range(2):
                        pin = pins[j]
                        if j == 0:
                            x_offset = pin.rx() - 0.5 * left_inst.mod.gate_fill_width
                            self.add_rect(METAL3, offset=vector(x_offset, via_y - 0.5 * self.m3_width),
                                          width=max(self.m3_width, x_offset - pin.cx()))
                        else:
                            x_offset = pin.lx() + 0.5 * left_inst.mod.gate_fill_width
                            self.add_rect(METAL3, offset=vector(pin.cx(), via_y - 0.5 * self.m3_width),
                                          width=max(self.m3_width, x_offset - pin.cx()))

                        offset = vector(x_offset, pin.cy())
                        self.add_contact_center(m1m2.layer_stack, offset=offset)
                        self.add_contact_center(m2m3.layer_stack, offset=offset)
                        self.add_rect_center(METAL2, offset=offset, height=left_inst.mod.gate_fill_height,
                                             width=left_inst.mod.gate_fill_width)
                        self.add_rect(METAL3, offset=vector(x_offset - 0.5 * self.m3_width,
                                                            pin.cy()),
                                      height=via_y + 0.5 * self.m3_width - pin.cy())

    def route_vdd_gnd(self):
        left_inst = min(self.inv_inst[:2], key=lambda x: x.lx())
        self.power_rail_x = left_inst.get_pin("gnd").lx()
        self.row_decoder_min_y = left_inst.get_pin("vdd").by()
        super().route_vdd_gnd()

    def copy_power_pin(self, pin):
        if pin.uy() <= self.row_decoder_min_y:
            x_offset = 0
        else:
            x_offset = self.power_rail_x
        self.add_layout_pin(pin.name, pin.layer, offset=vector(x_offset, pin.by()),
                            width=self.width - x_offset, height=pin.height())
