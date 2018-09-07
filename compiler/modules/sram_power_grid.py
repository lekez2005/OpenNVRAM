
import contact
from contact_full_stack import ContactFullStack
import utils
from vector import vector

import design

#class Mixin(design.design):
class Mixin:

    def route_one_bank_power(self):

        m1mbottop = ContactFullStack(start_layer=0, stop_layer=1, centralize=False, dimensions=[[1, 5]]) # e.g M1-M9
        top_power_layer = self.bank_inst.mod.top_power_layer
        bottom_power_layer = self.bank_inst.mod.bottom_power_layer

        control_logic_pins = map(lambda x: self.control_logic_inst.get_pin(x).by(), self.control_logic_outputs)

        control_vdd = self.control_logic_inst.get_pin("vdd")
        bank_left_vdd = min(self.bank_inst.get_pins("vdd"), key=lambda x: x.lx())

        max_y = min(control_logic_pins) - 2*self.m3_space - m1mbottop.second_layer_height
        min_y = control_vdd.by()

        vdd_grid_bottom = map(lambda x: x.offset, self.bank_inst.mod.vdd_grid_rects)
        vdd_via_pos = map(lambda x: utils.transform_relative(x, self.bank_inst).y, vdd_grid_bottom)
        vdd_via_pos = filter(lambda x: max_y > x > min_y, vdd_via_pos)



        for via_pos in vdd_via_pos:
            self.add_rect(bottom_power_layer, offset=(control_vdd.lx(), via_pos),
                          height=m1mbottop.second_layer_height,
                          width=bank_left_vdd.cx() - control_vdd.lx())
            self.add_inst(m1mbottop.name, m1mbottop,
                          offset=(control_vdd.lx(), via_pos))
            self.connect_inst([])
        self.add_layout_pin("vdd", layer=top_power_layer, offset=bank_left_vdd.ll(),
                            width=bank_left_vdd.width(), height=bank_left_vdd.height())

        gnd_grid_bottom = map(lambda x: x.offset, self.bank_inst.mod.gnd_grid_rects)
        gnd_via_pos = map(lambda x: utils.transform_relative(x, self.bank_inst).y, gnd_grid_bottom)
        gnd_via_pos = filter(lambda x: max_y > x > min_y, gnd_via_pos)

        bank_gnd = self.bank_inst.get_pin("gnd")
        control_gnd = self.control_logic_inst.get_pin("gnd")

        for via_pos in gnd_via_pos:
            self.add_rect(bottom_power_layer, offset=(control_gnd.lx(), via_pos),
                          height=m1mbottop.second_layer_height,
                          width=bank_gnd.cx() - control_gnd.lx())
            self.add_inst(m1mbottop.name, m1mbottop,
                          offset=(control_gnd.lx(), via_pos))
            self.connect_inst([])

        self.add_layout_pin("gnd", layer=top_power_layer, offset=bank_gnd.ll(),
                            width=bank_gnd.width(), height=bank_gnd.height())




        control_gnd = self.control_logic_inst.get_pin("gnd")
        bank_gnd = self.bank_inst.get_pin("gnd")
        connection_height = 3 * self.m2_width
        connection_offset = control_gnd.ul() - vector(0, connection_height)
        self.add_rect("metal2", height=connection_height, width=bank_gnd.lx() - control_gnd.lx(),
                      offset=connection_offset)
        self.add_via_center(layers=("metal1", "via1", "metal2"),
                            offset=vector(control_gnd.cx(), control_gnd.uy() - 0.5 * connection_height))

    def route_bank_supply_rails(self, bottom_banks):
        """ Create rails at bottom. Connect veritcal rails to top and bottom. """

        # add bottom metal1 gnd rail across both banks
        self.add_rect(layer="metal1",
                      offset=vector(0, self.power_rail_pitch),
                      height=self.power_rail_width,
                      width=self.width)
        # add bottom metal3 rail across both banks
        self.add_rect(layer="metal3",
                      offset=vector(0, 0),
                      height=self.power_rail_width,
                      width=self.width)

        left_bank = self.bank_inst[bottom_banks[0]]


        top_power_layer = left_bank.mod.top_power_layer
        # add vdd pin
        mid_vdd = max(filter(lambda x: x.layer == "metal1", left_bank.get_pins("vdd")),
                      key=lambda x: x.lx())
        self.add_layout_pin("vdd", layer=top_power_layer, offset=mid_vdd.ll(),
                            width=mid_vdd.width(), height=mid_vdd.height())


        # add gnd pin
        left_gnd = filter(lambda x: x.layer == "metal2", left_bank.get_pins("gnd"))[0]
        self.add_layout_pin("gnd", layer=top_power_layer, offset=left_gnd.ll(),
                            width=left_gnd.width(), height=left_gnd.height())

        # route bank vertical rails to bottom
        for i in bottom_banks:
            vdd_pins = self.bank_inst[i].get_pins("vdd")
            for vdd_pin in vdd_pins:
                vdd_pos = vdd_pin.ul()
                # Route to bottom
                self.add_rect(layer="metal1",
                              offset=vector(vdd_pos.x, self.power_rail_pitch),
                              height=self.horz_control_bus_positions["vdd"].y - self.power_rail_pitch,
                              width=vdd_pin.width())

            gnd_pins = self.bank_inst[i].get_pins("gnd")
            for gnd_pin in gnd_pins:
                gnd_pos = gnd_pin.ul()
                # Route to bottom
                self.add_rect(layer="metal2",
                              offset=vector(gnd_pos.x, 0),
                              height=self.horz_control_bus_positions["gnd"].y,  # route to the top bank
                              width=gnd_pin.width())
                # Add vias at top
                right_rail_pos = vector(gnd_pin.cx(), self.horz_control_bus_positions["gnd"].y)
                self.add_via_center(layers=("metal1", "via1", "metal2"),
                                    offset=right_rail_pos,
                                    rotate=90,
                                    size=[1, 3])
                # Add vias at bottom
                right_rail_pos = vector(gnd_pin.lr().x, 0)
                self.add_via(layers=("metal2", "via2", "metal3"),
                             offset=right_rail_pos,
                             rotate=90,
                             size=[2, 3])

    def route_two_banks_power(self, bottom_banks):
        """ Create rails at bottom. Connect veritcal rails to top and bottom. """

        self.route_bank_supply_rails(bottom_banks)

        left_bank = self.bank_inst[bottom_banks[0]]
        right_bank = self.bank_inst[bottom_banks[1]]

        m1mbottop = ContactFullStack(start_layer=0, stop_layer=1, centralize=False, dimensions=[[1, 5]])  # e.g M1-M9

        # connect the bank MSB flop supplies and control vdd
        vdd_pins = self.msb_address_inst.get_pins("vdd") + self.control_logic_inst.get_pins("vdd")
        bank1_vdd = max(left_bank.get_pins("vdd"), key=lambda x: x.rx())
        for vdd_pin in vdd_pins:
            if vdd_pin.layer != "metal1": continue
            self.add_rect("metal1", height=vdd_pin.height(),
                          width=vdd_pin.lx() - bank1_vdd.rx(),
                          offset=vector(bank1_vdd.rx(), vdd_pin.by()))

        # connect vdd grid rails across both banks

        bottom_power_layer = left_bank.mod.bottom_power_layer

        left_vdd = min(filter(lambda x: x.layer == "metal1", left_bank.get_pins("vdd")),
                           key=lambda x: x.lx())
        right_vdd = max(filter(lambda x: x.layer == "metal1", right_bank.get_pins("vdd")),
                            key=lambda x: x.rx())

        rail_width = right_vdd.lx() - left_vdd.lx()

        vdd_grid_rects = left_bank.mod.vdd_grid_rects
        vdd_via_pos_y = map(lambda x: utils.transform_relative(x.offset, left_bank).y, vdd_grid_rects)
        vdd_via_pos_y = [x - m1mbottop.second_layer_height for x in vdd_via_pos_y]  # substract since banks are mirrored
        for via_pos_y in vdd_via_pos_y:
            self.add_rect(bottom_power_layer, offset=vector(left_vdd.cx(), via_pos_y),
                          height=m1mbottop.second_layer_height,
                          width=rail_width)

        # connect msb ground to control_logic ground
        gnd_pins = self.msb_address_inst.get_pins("gnd")
        control_gnd = self.control_logic_inst.get_pin("gnd")

        # extend control ground to top msb ground
        top_msb_gnd = max(gnd_pins, key=lambda x: x.uy())
        self.add_rect("metal1", width=control_gnd.width(),
                                  height=top_msb_gnd.uy() - control_gnd.uy(),
                                  offset=control_gnd.ul())
        for gnd_pin in gnd_pins:
            if gnd_pin.layer != "metal1": continue
            self.add_rect("metal1", height=gnd_pin.height(),
                          width=control_gnd.lx() - gnd_pin.rx(),
                          offset=gnd_pin.lr())

        # connect gnd grid rails across both banks

        control_logic_pins = map(lambda x: self.control_logic_inst.get_pin(x).by(), self.control_logic_outputs)
        min_y = max(control_logic_pins) + 2 * self.m3_space + m1mbottop.second_layer_height

        left_gnd = filter(lambda x: x.layer == "metal2", left_bank.get_pins("gnd"))[0]
        right_gnd = filter(lambda x: x.layer == "metal2", right_bank.get_pins("gnd"))[0]


        rail_width = right_gnd.lx() - left_gnd.lx()

        gnd_grid_rects = left_bank.mod.gnd_grid_rects
        gnd_via_pos_y = map(lambda x: utils.transform_relative(x.offset, left_bank).y, gnd_grid_rects)
        gnd_via_pos_y = [x - m1mbottop.second_layer_height for x in gnd_via_pos_y]
        for via_pos_y in gnd_via_pos_y:
            self.add_rect(bottom_power_layer, offset=vector(left_gnd.cx(), via_pos_y),
                          height=m1mbottop.second_layer_height,
                          width=rail_width)
            if min_y < via_pos_y < top_msb_gnd.uy():
                self.add_inst(m1mbottop.name, m1mbottop,
                              offset=(control_gnd.lx(), via_pos_y))
                self.connect_inst([])


    def route_four_banks_power(self):
        self.route_bank_supply_rails(bottom_banks=[2, 3])

        # connect msb_address, decoder and control_logic vdd pins
        vdd_pins = self.msb_address_inst.get_pins("vdd") + self.msb_decoder_inst.get_pins("vdd") + \
                   self.control_logic_inst.get_pins("vdd")
        bank1_vdd = max((self.bank_inst[0]).get_pins("vdd"), key=lambda x: x.rx())
        for vdd_pin in vdd_pins:
            if vdd_pin.layer != "metal1": continue
            self.add_rect("metal1", height=vdd_pin.height(),
                          width=vdd_pin.lx() - bank1_vdd.rx(),
                          offset=vector(bank1_vdd.rx(), vdd_pin.by()))

        # connect msb_address, decoder and control_logic vdd pins
        gnd_pins = self.msb_address_inst.get_pins("gnd") + self.msb_decoder_inst.get_pins("gnd")
        gnd_pins = filter(lambda x: x.layer == "metal1", gnd_pins)
        right_most_pin = max(gnd_pins, key=lambda x: x.rx())
        bottom_gnd = min(gnd_pins, key=lambda x: x.by())
        top_gnd = max(gnd_pins, key=lambda x: x.by())
        x_extension = 2 * self.m1_space
        for gnd_pin in gnd_pins:
            self.add_rect("metal1", height=gnd_pin.height(),
                          width=right_most_pin.rx() - gnd_pin.rx() + x_extension,
                          offset=gnd_pin.lr())
        self.add_rect("metal1", offset=vector(right_most_pin.rx() + x_extension, bottom_gnd.by()),
                      width=bottom_gnd.height(),
                      height=top_gnd.uy() - bottom_gnd.by())

        # connect control gnd
        control_gnd = filter(lambda x: x.layer == "metal1", self.control_logic_inst.get_pins("gnd"))[0]

        m1mbottop = ContactFullStack(start_layer=0, stop_layer=1, centralize=False, dimensions=[[1, 5]])  # e.g M1-M9

        top_left_bank = self.bank_inst[0]
        bottom_left_bank = self.bank_inst[2]

        bottom_power_layer = top_left_bank.mod.bottom_power_layer

        left_vdd = min(filter(lambda x: x.layer == "metal1", top_left_bank.get_pins("vdd")),
                       key=lambda x: x.lx())
        right_vdd = max(filter(lambda x: x.layer == "metal1", self.bank_inst[1].get_pins("vdd")),
                        key=lambda x: x.rx())

        rail_width = right_vdd.lx() - left_vdd.lx()

        vdd_grid_rects = bottom_left_bank.mod.vdd_grid_rects
        vdd_via_pos_y = map(lambda x: utils.transform_relative(x.offset, bottom_left_bank).y, vdd_grid_rects)
        vdd_via_pos_y = [x - m1mbottop.second_layer_height for x in vdd_via_pos_y]  # substract since banks are mirrored
        vdd_grid_rects = top_left_bank.mod.vdd_grid_rects
        vdd_via_pos_y += map(lambda x: utils.transform_relative(x.offset, top_left_bank).y, vdd_grid_rects)

        for via_pos_y in vdd_via_pos_y:
            self.add_rect(bottom_power_layer, offset=vector(left_vdd.cx(), via_pos_y),
                          height=m1mbottop.second_layer_height,
                          width=rail_width)

        left_gnd = filter(lambda x: x.layer == "metal2", top_left_bank.get_pins("gnd"))[0]
        right_gnd = filter(lambda x: x.layer == "metal2", self.bank_inst[1].get_pins("gnd"))[0]
        rail_width = right_gnd.lx() - left_gnd.lx()
        rail_height = m1mbottop.second_layer_height

        gnd_grid_rects = bottom_left_bank.mod.gnd_grid_rects
        gnd_via_pos_y = map(lambda x: utils.transform_relative(x.offset, bottom_left_bank).y, gnd_grid_rects)
        gnd_via_pos_y = [x - m1mbottop.second_layer_height for x in gnd_via_pos_y]  # substract since banks are mirrored
        gnd_grid_rects = top_left_bank.mod.gnd_grid_rects
        gnd_via_pos_y += map(lambda x: utils.transform_relative(x.offset, top_left_bank).y, gnd_grid_rects)

        control_logic_pins = map(lambda x: self.control_logic_inst.get_pin(x).by(), self.control_logic_outputs)
        max_ctrl_y = max(control_logic_pins) + 2 * self.m3_space + m1mbottop.second_layer_height
        min_ctrl_y = min(control_logic_pins) - 2 * self.m3_space - m1mbottop.second_layer_height

        for via_pos_y in gnd_via_pos_y:
            if bottom_gnd.by() + rail_height < via_pos_y < top_gnd.uy() - rail_height:
                self.add_inst(m1mbottop.name, m1mbottop,
                              offset=(right_most_pin.rx() + x_extension, via_pos_y))
                self.connect_inst([])
            elif control_gnd.by() + rail_height < via_pos_y < control_gnd.uy() - rail_height:
                if not min_ctrl_y < via_pos_y < max_ctrl_y:
                    self.add_inst(m1mbottop.name, m1mbottop,
                                  offset=(control_gnd.lx(), via_pos_y))
                    self.connect_inst([])
            self.add_rect(bottom_power_layer, offset=vector(left_gnd.cx(), via_pos_y),
                          height=rail_height,
                          width=rail_width)



        # connect the banks to the vertical address bus
        # connect the banks to the vertical control bus
        for n in self.addr_bus_names + self.control_bus_names:
            # Skip these from the horizontal bus
            if n in ["vdd", "gnd"]: continue
            # This will be the bank select, so skip it
            if n in self.msb_bank_sel_addr: continue

            for bank_id in [0, 2]:
                pin0_pos = self.bank_inst[bank_id].get_pin(n).rc()
                pin1_pos = self.bank_inst[bank_id + 1].get_pin(n).lc()
                rail_pos = vector(self.vert_control_bus_positions[n].x, pin0_pos.y)
                self.add_path("metal3", [pin0_pos, pin1_pos])
                if n in self.addr_bus_names:
                    self.add_via_center(("metal3", "via3", "metal4"), rail_pos, rotate=90)
                else:
                    self.add_via_center(("metal3", "via3", "metal4"), rail_pos)



        # connect top and bottom bank rails
        top_left_vdd = min(filter(lambda x: x.layer == "metal1", self.bank_inst[0].get_pins("vdd")),
                           key=lambda x: x.lx())
        bottom_left_vdd = min(filter(lambda x: x.layer == "metal1", self.bank_inst[2].get_pins("vdd")),
                              key=lambda x: x.lx())
        top_right_vdd = max(filter(lambda x: x.layer == "metal1", self.bank_inst[1].get_pins("vdd")),
                            key=lambda x: x.rx())
        bottom_right_vdd = max(filter(lambda x: x.layer == "metal1", self.bank_inst[3].get_pins("vdd")),
                               key=lambda x: x.rx())

        top_left_gnd = min(filter(lambda x: x.layer == "metal2", self.bank_inst[0].get_pins("gnd")),
                           key=lambda x: x.lx())
        bottom_left_gnd = min(filter(lambda x: x.layer == "metal2", self.bank_inst[2].get_pins("gnd")),
                              key=lambda x: x.lx())
        top_right_gnd = max(filter(lambda x: x.layer == "metal2", self.bank_inst[1].get_pins("gnd")),
                            key=lambda x: x.rx())
        bottom_right_gnd = max(filter(lambda x: x.layer == "metal2", self.bank_inst[3].get_pins("gnd")),
                               key=lambda x: x.rx())

        for (top, bottom) in [(top_left_vdd, bottom_left_vdd), (top_right_vdd, bottom_right_vdd),
                              (top_left_gnd, bottom_left_gnd), (top_right_gnd, bottom_right_gnd)]:
            self.add_rect(bottom.layer, offset=bottom.ul(), width=bottom.width(),
                          height=top.by() - bottom.uy())

        left_vdd = max(filter(lambda x: x.layer == "metal1", self.bank_inst[0].get_pins("vdd")),
                       key=lambda x: x.lx())

        right_vdd = min(filter(lambda x: x.layer == "metal1", self.bank_inst[1].get_pins("vdd")),
                        key=lambda x: x.rx())

        bottom_y_offset = self.horz_control_bus_positions["vdd"].y
        for vdd_pin in [left_vdd, right_vdd]:
            enclosure = 0.5 * self.m2_width
            self.add_via_center(layers=("metal1", "via1", "metal2"),
                                offset=vector(vdd_pin.cx(), bottom_y_offset - enclosure),
                                rotate=90,
                                size=[1, 2])
            self.add_via_center(layers=("metal1", "via1", "metal2"),
                                offset=vector(vdd_pin.cx(),
                                              vdd_pin.by() + 0.5 * contact.m1m2.first_layer_width + enclosure),
                                rotate=90,
                                size=[1, 2])
            rect_height = vdd_pin.by() + 2 * enclosure + contact.m1m2.first_layer_width - \
                          (bottom_y_offset - enclosure - 0.5 * contact.m1m2.first_layer_width - enclosure)
            self.add_rect("metal2", width=vdd_pin.width(),
                          height=rect_height,
                          offset=vector(vdd_pin.lx(), bottom_y_offset
                                        - 0.5 * contact.m1m2.first_layer_width - 2 * enclosure))
