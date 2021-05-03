from base.contact import m1m2, m2m3
from base.design import METAL1, METAL2, METAL3, design
from base.vector import vector
from base.well_implant_fills import create_wells_and_implants_fills
from globals import OPTS
from modules.logic_buffer import LogicBuffer
from modules.wordline_driver_array import wordline_driver_array


class stacked_wordline_driver_array(wordline_driver_array):
    def __init__(self, name, rows, buffer_stages=None):
        design.__init__(self, name)
        self.rows = rows
        self.buffer_stages = buffer_stages

        self.buffer_insts = []
        self.module_insts = []

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def create_layout(self):
        super().create_layout()
        self.width = self.buffer_insts[1].rx()
        self.create_power_pins()

    def create_modules(self):
        c = __import__(OPTS.bitcell)
        mod_bitcell = getattr(c, OPTS.bitcell)
        bitcell = mod_bitcell()

        self.logic_buffer = LogicBuffer(self.buffer_stages, logic="pnand2",
                                        height=2 * bitcell.height, route_outputs=False,
                                        route_inputs=False,
                                        contact_pwell=False, contact_nwell=False, align_bitcell=True)
        self.add_mod(self.logic_buffer)

    def add_modules(self):
        en_pin_x = self.get_parallel_space(METAL1) + self.m1_width
        self.en_pin_clearance = en_pin_clearance = (en_pin_x + self.m2_width +
                                                    self.get_parallel_space(METAL2))

        self.height = 0.5 * self.logic_buffer.height * self.rows

        rail_y = - 0.5 * self.rail_height
        en_rail = self.add_rect(METAL2, offset=vector(en_pin_x, rail_y), width=self.m2_width,
                                height=self.height)

        en_pin = self.add_layout_pin(text="en", layer="metal2",
                                     offset=vector(en_pin_clearance + self.logic_buffer.width +
                                                   en_pin_x, rail_y),
                                     width=self.m2_width, height=self.height)
        # join en rail and en_pin
        y_offset = en_rail.by() - self.m3_width
        self.add_rect(METAL3, offset=vector(en_rail.lx(), y_offset),
                      width=en_pin.lx() - en_rail.lx())
        self.add_contact(m2m3.layer_stack, offset=vector(en_rail.lx() + m2m3.height, y_offset),
                         rotate=90)
        self.add_contact(m2m3.layer_stack, offset=vector(en_pin.rx(), y_offset),
                         rotate=90)

        x_offsets = [en_pin_clearance, 2 * en_pin_clearance + self.logic_buffer.width]

        fill_rects = create_wells_and_implants_fills(
            self.logic_buffer.buffer_mod.module_insts[-1].mod,
            self.logic_buffer.logic_mod)

        for row in range(self.rows):
            if (row % 4) < 2:
                y_offset = self.logic_buffer.height * (int(row / 2) + 1)
                mirror = "MX"
            else:
                y_offset = self.logic_buffer.height * int(row / 2)
                mirror = "R0"
            x_offset = x_offsets[row % 2]
            # add logic buffer
            buffer_inst = self.add_inst("driver{}".format(row), mod=self.logic_buffer,
                                        offset=vector(x_offset, y_offset), mirror=mirror)
            self.connect_inst(["en", "in[{}]".format(row), "wl_bar[{}]".format(row),
                               "wl[{}]".format(row), "vdd", "gnd"])

            m3_clearance = 0.5 * self.rail_height + self.get_parallel_space(METAL3)
            m3_pitch = self.m3_width + self.get_parallel_space(METAL3)
            if row % 2 == 0:
                in_y_offset = buffer_inst.by() + m3_clearance + m3_pitch
            else:
                in_y_offset = buffer_inst.uy() - m3_clearance - self.m3_width - m3_pitch

            # decoder in
            b_pin = buffer_inst.get_pin("B")
            self.add_layout_pin("in[{}]".format(row), METAL3,
                                offset=vector(0, in_y_offset),
                                width=b_pin.cx() + 0.5 * self.m3_width)
            self.add_rect(METAL3, offset=vector(b_pin.cx() - 0.5 * self.m3_width, in_y_offset),
                          height=b_pin.cy() - in_y_offset)
            self.add_contact_center(m1m2.layer_stack, offset=b_pin.center())
            self.add_contact_center(m2m3.layer_stack, offset=b_pin.center())
            fill_width = self.logic_buffer.logic_mod.gate_fill_width
            fill_height = self.logic_buffer.logic_mod.gate_fill_height
            self.add_rect_center(METAL2, offset=b_pin.center(),
                                 width=fill_width, height=fill_height)

            # route en input pin
            rail = en_rail if row % 2 == 0 else en_pin
            a_pin = buffer_inst.get_pin("A")
            self.add_contact(m1m2.layer_stack,
                             offset=vector(rail.lx(), a_pin.cy() - 0.5 * m1m2.height))
            self.add_rect(METAL1, offset=vector(rail.lx(), a_pin.cy() - 0.5 * self.m1_width),
                          width=a_pin.lx() - rail.lx())

            self.buffer_insts.append(buffer_inst)

            self.copy_layout_pin(buffer_inst, "out", "wl[{}]".format(row))

            # Join adjacent rects between left and right buffers
            if row % 4 in [1, 3]:
                continue

            for fill_rect in fill_rects:
                if row % 4 == 0:
                    #
                    fill_rect = (fill_rect[0], self.logic_buffer.height - fill_rect[2],
                                 self.logic_buffer.height - fill_rect[1])
                elif row % 4 == 2:
                    pass
                else:
                    continue
                y_shift = int(row / 2) * self.logic_buffer.height
                self.add_rect(fill_rect[0], offset=vector(buffer_inst.rx(),
                                                          y_shift + fill_rect[1]),
                              height=fill_rect[2] - fill_rect[1],
                              width=x_offsets[1] - buffer_inst.rx())

    def create_power_pins(self):
        all_pins = []
        for i in range(0, self.rows, 4):
            all_pins.append(self.buffer_insts[i].get_pin("vdd"))
            all_pins.append(self.buffer_insts[i].get_pin("gnd"))
        all_pins.append(self.buffer_insts[-2].get_pin("vdd"))

        pin_right = self.buffer_insts[1].get_pin("vdd").rx()
        for pin in all_pins:
            self.add_layout_pin(pin.name, pin.layer, pin.ll(),
                                height=pin.height(), width=pin_right - pin.lx())
