from base.contact import cross_m2m3, m1m2, cross_m1m2
from base.design import METAL2, METAL3, METAL1
from base.hierarchy_layout import GDS_ROT_270
from base.pin_layout import pin_layout
from base.vector import vector
from globals import OPTS
from modules.control_buffers import ControlBuffers
from modules.push_rules.buffer_stages_horizontal import BufferStagesHorizontal
from modules.push_rules.logic_buffer_horizontal import LogicBufferHorizontal
from modules.push_rules.pgate_horizontal_tap import pgate_horizontal_tap
from modules.push_rules.pinv_horizontal import pinv_horizontal
from modules.push_rules.pnand2_horizontal import pnand2_horizontal
from modules.push_rules.pnor2_horizontal import pnor2_horizontal


class LatchedControlLogic(ControlBuffers):
    """
    Generate and buffer control signals using bank_sel, clk and read, sense_trig and precharge_trig
    Assumes
    Inputs:
        bank_sel, read, clk, sense_trig, precharge_trig
    Define internal signal
        bank_sel_cbar = NAND(clk_bar, bank_sel)
    Outputs
        clk_buf:            bank_sel.clk
        wordline_en: and3((sense_trig_bar + read_bar), bank_sel, clk_bar)
                    = nor(bank_sel_cbar, nor(sense_trig_bar, read_bar))
                    = nor(bank_sel_cbar, and(sense_trig, read)) sense_trig = 0 during writes
                    =       nor(bank_sel_cbar, sense_trig)
        write_en:           and3(read_bar, clk_bar, bank_sel) = nor(read, bank_sel_cbar)
        precharge_en_bar: and2(bank_sel, precharge_trig)
        sampleb:    NAND4(bank_sel, sense_trig_bar, clk_bar, read)
                    = NAND2(AND(bank_sel.clk_bar, sense_trig_bar), read)
                    = NAND2(nor(bank_sel_cbar, sense_trig), read)
                    =       nand2( nor(bank_sel_cbar, sense_trig), read)
        sense_en: bank_sel.sense_trig (same as tri_en)
        tri_en_bar: sense_en_bar
    """
    rotation_for_drc = GDS_ROT_270

    def __init__(self, is_left_bank=False):
        self.is_left_bank = is_left_bank
        if is_left_bank:
            self.name += "_left"
        super().__init__()

    def add_pins(self):
        wordline = [] if self.is_left_bank else ["wordline_en"]
        self.add_pin_list(["bank_sel", "read", "clk", "sense_trig", "precharge_trig",
                           "clk_buf", "clk_bar"]
                          + wordline +
                          ["precharge_en_bar", "write_en", "sense_en",
                           "tri_en", "sample_bar", "vdd", "gnd"])

    def get_num_rails(self):
        return 5

    def calculate_rail_positions(self):

        y_base = (self.inv.height + 0.5 * self.inv.get_pin("vdd").height()
                  + self.get_parallel_space(METAL3))

        for i in range(len(self.rail_pos)):
            self.rail_pos[i] = y_base + i * self.bus_pitch

        self.mod_y_offsets = [self.inv.height,
                              self.rail_pos[-1] + self.bus_pitch + 0.5 * self.rail_height]

        self.height = self.mod_y_offsets[1] + self.inv.height
        self.mid_y = 0.5 * self.height
        self.forbidden_m2 = []

    def get_all_mods(self):
        mods = ["clk_buf", "precharge_buf", "nand2", "body_tap", "inv", "nand2",
                "wordline_buf", "write_buf", "nor2", "sample_bar", "body_tap",
                "sense_amp_buf", "tri_en_buf"]
        if self.is_left_bank:
            mods.remove("wordline_buf")
        return mods

    def get_z_b_pairs(self):
        """Get direct z pin to b pin connection to prevent splitting for adjacent modules"""
        if self.is_left_bank:
            return [(4, 5), (7, 8)]
        return [(4, 5, 6), (8, 9)]

    def calculate_split_index(self):
        all_mods = self.get_all_mods()
        z_b_pairs = list(sorted(self.get_z_b_pairs(), key=lambda x: x[0]))
        groups = []
        i = 0
        while i < len(all_mods):
            if len(z_b_pairs) > 0 and i in z_b_pairs[0]:
                groups.append(z_b_pairs[0])
                i = z_b_pairs[0][-1] + 1
                z_b_pairs.pop(0)
            else:
                groups.append((i,))
                i += 1
        widths = []
        for group in groups:
            group_widths = [getattr(self, all_mods[x]).width for x in group]
            widths.append(sum(group_widths))

        # get split index
        split_widths = []
        for i in range(1, len(all_mods) - 1):
            width = max(sum(widths[:i]), sum(widths[i:]))
            split_widths.append(width)
        self.width = min(split_widths)
        group_split_index = split_widths.index(min(split_widths))
        self.split_index = groups[group_split_index][-1] + 1

        x_offset = 0.0
        all_offsets = []
        widths = [getattr(self, all_mods[x]).width for x in range(len(all_mods))]
        for j in range(len(groups)):
            for i in groups[j]:
                if i < self.split_index:
                    all_offsets.append(x_offset)
                    x_offset += widths[i]
                else:
                    if i == self.split_index:
                        x_offset = self.width
                    all_offsets.append(x_offset)
                    if i < len(all_mods) - 1:
                        x_offset -= widths[i]
        self.mod_x_offsets = all_offsets

    def get_module_offset(self):
        """Keeps track of how many times is has been called and uses the module order specified
        to decide the offset and mirror of a module"""
        x_offset = self.mod_x_offsets[self.mod_index]

        if self.mod_index < self.split_index:
            y_offset = self.mod_y_offsets[1]
            mirror = ""
        else:
            y_offset = self.mod_y_offsets[0]
            mirror = "XY"

        self.mod_index += 1
        return x_offset, y_offset, mirror

    def add_module(self, name, mod):
        x_offset, y_offset, mirror = self.get_module_offset()
        inst = self.add_inst(name, mod=mod, offset=vector(x_offset, y_offset),
                             mirror=mirror)
        return inst

    def create_modules(self):
        self.inv = pinv_horizontal(size=1)
        self.add_mod(self.inv)

        self.body_tap = pgate_horizontal_tap(self.inv)

        self.logic_heights = self.inv.height

        self.nand2 = pnand2_horizontal(size=1)
        self.add_mod(self.nand2)

        self.nor2 = pnor2_horizontal(size=1)
        self.add_mod(self.nor2)

        self.clk_buf = LogicBufferHorizontal(buffer_stages=OPTS.clk_buffers, logic="pnand2")
        self.add_mod(self.clk_buf)

        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        self.precharge_buf = LogicBufferHorizontal(OPTS.precharge_buffers, "pnand2")
        self.add_mod(self.precharge_buf)

        if not self.is_left_bank:
            assert len(OPTS.wordline_en_buffers) % 2 == 0, "Number of wordline buffers should be even"
            self.wordline_buf = LogicBufferHorizontal(OPTS.wordline_en_buffers, "pnor2")
            self.add_mod(self.wordline_buf)

        assert len(OPTS.wordline_en_buffers) % 2 == 0, "Number of write buffers should be even"
        self.write_buf = LogicBufferHorizontal(OPTS.write_buffers, "pnor2")
        self.add_mod(self.write_buf)

        assert len(OPTS.sampleb_buffers) % 2 == 0, "Number of sampleb buffers should be even"
        self.sample_bar = LogicBufferHorizontal(OPTS.sampleb_buffers, "pnand2")
        self.add_mod(self.sample_bar)

        assert len(OPTS.sense_amp_buffers) % 2 == 1, "Number of sense_en buffers should be odd"
        self.sense_amp_buf = BufferStagesHorizontal(OPTS.sense_amp_buffers)
        self.add_mod(self.sense_amp_buf)

        assert len(OPTS.tri_en_buffers) % 2 == 1, "Number of tri_en buffers should be odd"
        self.tri_en_buf = BufferStagesHorizontal(OPTS.tri_en_buffers)
        self.add_mod(self.tri_en_buf)

    def add_modules(self):

        self.mod_index = 0
        self.calculate_split_index()

        self.clk_buf_inst = self.add_module("clk_buf", mod=self.clk_buf)
        self.connect_inst(["bank_sel", "clk", "clk_buf", "clk_bar", "vdd", "gnd"])

        self.precharge_buf_inst = self.add_module("precharge_buf", mod=self.precharge_buf)
        self.connect_inst(["bank_sel", "precharge_trig", "precharge_en",
                           "precharge_en_bar", "vdd", "gnd"])

        self.sel_trig_inst = self.add_module("sel_trig", mod=self.nand2)
        self.connect_inst(["bank_sel", "sense_trig", "sel_trig_bar", "vdd", "gnd"])

        self.body_tap_inst = self.add_module(self.body_tap.name, mod=self.body_tap)
        self.connect_inst([])

        self.clk_bar_inst = self.add_module("clk_bar", mod=self.inv)
        self.connect_inst(["clk", "clk_bar_int", "vdd", "gnd"])

        self.bank_sel_cbar_inst = self.add_module("bank_sel_cbar", mod=self.nand2)
        self.connect_inst(["bank_sel", "clk_bar_int", "bank_sel_cbar", "vdd", "gnd"])

        if not self.is_left_bank:
            self.wordline_buf_inst = self.add_module("wordline_buf", mod=self.wordline_buf)
            self.connect_inst(["sense_trig", "bank_sel_cbar",
                               "wordline_en_bar", "wordline_en", "vdd", "gnd"])

        self.write_buf_inst = self.add_module("write_buf", mod=self.write_buf)
        self.connect_inst(["read", "bank_sel_cbar", "write_en", "write_en_bar", "vdd", "gnd"])

        self.sel_cbar_trig_inst = self.add_module("sel_cbar_trig", mod=self.nor2)
        self.connect_inst(["sense_trig", "bank_sel_cbar", "sel_cbar_trig", "vdd", "gnd"])

        self.sample_bar_inst = self.add_module("sample_bar", mod=self.sample_bar)
        self.connect_inst(["read", "sel_cbar_trig", "sample_en_buf", "sample_bar", "vdd", "gnd"])

        self.body_tap_inst2 = self.add_module(self.body_tap.name, mod=self.body_tap)
        self.connect_inst([])

        self.sense_amp_buf_inst = self.add_module("sense_amp_buf", mod=self.sense_amp_buf)
        self.connect_inst(["sel_trig_bar", "sense_en", "sense_en_bar", "vdd", "gnd"])

        self.tri_en_buf_inst = self.add_module("tri_en_buf", mod=self.tri_en_buf)
        self.connect_inst(["sel_trig_bar", "tri_en", "tri_en_bar", "vdd", "gnd"])

    def get_net_x_range(self, net_name):
        """Returns the x offset range for which a module is connected to the net"""

        def get_pin_x(inst, pin_name="A"):
            pin = inst.get_pin(pin_name)
            if pin.cy() > self.rail_pos[0]:
                return pin.cx()
            else:
                return pin.cx()

        max_x = 0
        min_x = self.width
        for i in range(len(self.conns)):
            if net_name in self.conns[i]:
                pin_index = self.conns[i].index(net_name)
                mod_pin = self.insts[i].mod.pins[pin_index]
                x_offset = get_pin_x(self.insts[i], mod_pin)
                max_x = max(max_x, x_offset)
                min_x = min(min_x, x_offset)
        return min_x, max_x

    def get_input_pins(self):
        return ["bank_sel", "clk", "read", "sense_trig", "precharge_trig"]

    def add_input_pin(self, pin_name):
        all_pins = self.get_input_pins()
        sorted_pins = list(sorted(all_pins, key=lambda x: self.get_net_x_range(x)[1]))
        rail_start_index = self.get_num_rails() - len(all_pins)

        rail_index = sorted_pins.index(pin_name)
        _, max_x = self.get_net_x_range(pin_name)
        pin = self.add_layout_pin(pin_name, METAL3, height=self.bus_width,
                                  offset=vector(0, self.rail_pos[rail_start_index + rail_index]),
                                  width=max_x + 0.5 * max(cross_m2m3.width, cross_m2m3.height))
        return pin

    def add_input_pins(self):
        self.bank_sel_pin = self.add_input_pin("bank_sel")
        self.clk_pin = self.add_input_pin("clk")
        self.read_pin = self.add_input_pin("read")
        self.sense_trig_pin = self.add_input_pin("sense_trig")
        self.precharge_trig_pin = self.add_input_pin("precharge_trig")
        self.add_intermediate_rails()

    def add_intermediate_rails(self):
        rails = []
        rail_names = ["sel_trig_bar", "bank_sel_cbar"]
        output_pins = [self.sel_trig_inst.get_pin("Z"),
                       self.bank_sel_cbar_inst.get_pin("Z")]
        # start from lowest to minimize the risk of overlap
        for i in range(2):
            min_x, max_x = self.get_net_x_range(rail_names[i])
            extension = 0.5 * max(cross_m2m3.width, cross_m2m3.height)
            rail = self.add_rect(METAL1, offset=vector(min_x - extension, self.rail_pos[i]),
                                 width=max_x - min_x + 2 * extension, height=self.bus_width)
            rails.append(rail)
            pin = output_pins[i]
            if pin.cy() > self.rail_pos[0]:
                via_y = pin.by()
            else:
                via_y = pin.uy() - m1m2.height
            x_offset = pin.cx() - 0.5 * self.m2_width
            self.add_contact(m1m2.layer_stack, offset=vector(x_offset, via_y))
            self.add_cross_contact_center(cross_m1m2, vector(pin.cx(), rail.cy()), True)

            self.add_rect(METAL2, offset=vector(x_offset, rail.cy()),
                          height=via_y - rail.cy(), width=self.m2_width)
            self.forbidden_m2.append((x_offset, rail.cy()))

        self.sel_trig_rail, self.bank_sel_cbar_rail = rails

    def route_internal_signals(self):
        self.connect_pin_to_rail(self.clk_buf_inst, "A", self.bank_sel_pin)
        self.connect_pin_to_rail(self.clk_buf_inst, "B", self.clk_pin)

        self.connect_pin_to_rail(self.precharge_buf_inst, "A", self.bank_sel_pin)
        self.connect_pin_to_rail(self.precharge_buf_inst, "B", self.precharge_trig_pin)

        self.connect_pin_to_rail(self.sel_trig_inst, "A", self.bank_sel_pin)
        self.connect_pin_to_rail(self.sel_trig_inst, "B", self.sense_trig_pin)

        self.connect_pin_to_rail(self.clk_bar_inst, "A", self.clk_pin)

        self.connect_z_to_b(z_inst=self.clk_bar_inst, b_inst=self.bank_sel_cbar_inst)
        self.connect_pin_to_rail(self.bank_sel_cbar_inst, "A", self.bank_sel_pin)

        if not self.is_left_bank:
            self.connect_z_to_b(z_inst=self.bank_sel_cbar_inst, b_inst=self.wordline_buf_inst)
            self.connect_pin_to_rail(self.wordline_buf_inst, "A", self.sense_trig_pin)

        self.connect_pin_to_rail(self.write_buf_inst, "A", self.read_pin)
        self.connect_pin_to_rail(self.write_buf_inst, "B", self.bank_sel_cbar_rail)

        self.connect_pin_to_rail(self.sel_cbar_trig_inst, "A", self.sense_trig_pin)
        self.connect_pin_to_rail(self.sel_cbar_trig_inst, "B", self.bank_sel_cbar_rail)

        self.connect_z_to_b(z_inst=self.sel_cbar_trig_inst, b_inst=self.sample_bar_inst)
        self.connect_pin_to_rail(self.sample_bar_inst, "A", self.read_pin)

        self.connect_pin_to_rail(self.sense_amp_buf_inst, "in", self.sel_trig_rail)
        self.connect_pin_to_rail(self.tri_en_buf_inst, "in", self.sel_trig_rail)

    def find_m2_clearance(self, pin, desired_rail_y):
        """Find un-obstructed M2 x offset"""
        all_m2 = list(sorted(self.forbidden_m2, key=lambda x: x[0], reverse=True))
        via_space = self.parallel_via_space  # space for side by side via
        parallel_space = self.get_parallel_space(METAL2)  # space for parallel lines

        pitch = via_space + self.m2_width
        desired_x = pin.cx() - 0.5 * self.m2_width
        if desired_x > max(all_m2, key=lambda x: x[0])[0] + pitch:
            return desired_x
        for (x_offset, rail_y) in all_m2:
            if rail_y == desired_rail_y:
                pitch = via_space + self.m2_width
            else:
                pitch = parallel_space + self.m2_width
            if x_offset - desired_x >= pitch or rail_y > desired_rail_y + self.bus_pitch:
                # too far away on the right or above
                continue
            elif x_offset >= desired_x and x_offset - desired_x < pitch:  # to the right but too close
                desired_x = x_offset - pitch
                continue
            elif desired_x >= x_offset and desired_x - x_offset < pitch:  # to the left but too close
                desired_x = x_offset - pitch
                continue
            else:  # nothing close enough
                break
        return desired_x

    def connect_pin_to_rail(self, inst, pin_name, rail):
        if isinstance(rail, pin_layout):
            via = cross_m2m3
            via_rotate = False
        else:
            via = cross_m1m2
            via_rotate = True

        def make_connection(x_offset_, via_y_):
            self.add_cross_contact_center(via, vector(x_offset_ + 0.5 * self.m2_width, rail.cy()),
                                          rotate=via_rotate)
            self.add_rect(METAL2, offset=vector(x_offset_, rail.cy()),
                          height=via_y_ - rail.cy(), width=self.m2_width)
            self.add_contact(m1m2.layer_stack, offset=vector(x_offset_, via_y_))

        pin = inst.get_pin(pin_name)

        if pin.cy() > self.mid_y:  # direct connection
            x_offset = pin.cx() - 0.5 * self.m2_width
            make_connection(x_offset, pin.by())
            self.forbidden_m2.append((x_offset, rail.cy()))
        else:
            via_y = pin.uy() - m1m2.height
            x_offset = self.find_m2_clearance(pin, rail.cy())
            self.forbidden_m2.append((x_offset, rail.cy()))
            if x_offset == pin.cx() - 0.5 * self.m2_width:  # direct connection
                make_connection(x_offset, via_y)
            else:
                # extend rail to new x offset
                extension = 0.5 * max(cross_m2m3.width, cross_m2m3.height)
                if rail.lx() > x_offset - extension:
                    layer = METAL1 if via_rotate else METAL3
                    height = rail.height if via_rotate else rail.height()
                    self.add_rect(layer, offset=vector(x_offset - extension, rail.by()),
                                  width=rail.lx() - x_offset + extension, height=height)
                # find pin index and use to calculate y offset for m3 rail
                pin_index = inst.mod.pins.index(pin_name)
                rail_pitch = self.get_parallel_space(METAL3) + self.m3_width
                y_base = self.rail_pos[0] - rail_pitch
                y_offset = y_base - pin_index * rail_pitch
                # add vertical m2 rail to new y_offset
                self.add_cross_contact_center(via, vector(x_offset + 0.5 * self.m2_width, rail.cy()),
                                              rotate=via_rotate)

                _, m2_fill = self.calculate_min_m1_area(layer=METAL2)
                _, m3_fill = self.calculate_min_m1_area(layer=METAL3)

                m2_height = max(m2_fill, rail.cy() - y_offset)
                self.add_rect(METAL2, offset=vector(x_offset, y_offset), height=m2_height)
                # add horizontal m3 rail to pin x offset
                self.add_cross_contact_center(cross_m2m3,
                                              vector(x_offset + 0.5 * self.m2_width,
                                                     y_offset + 0.5 * self.m2_width),
                                              rotate=False)
                m3_width = max(m3_fill, pin.cx() - x_offset)
                self.add_rect(METAL3, offset=vector(x_offset, y_offset), width=m3_width)
                # add m2 to pin
                self.add_cross_contact_center(cross_m2m3,
                                              vector(pin.cx(), y_offset + 0.5 * self.m2_width),
                                              rotate=False)
                x_offset = pin.cx() - 0.5 * self.m2_width
                self.add_rect(METAL2, offset=vector(x_offset, y_offset),
                              height=via_y - y_offset, width=self.m2_width)
                self.add_contact(m1m2.layer_stack, offset=vector(x_offset, via_y))

    def connect_z_to_a(self, z_inst, a_inst, a_name="A", z_name="Z"):
        a_pin = a_inst.get_pin(a_name)
        z_pin = z_inst.get_pin(z_name)
        self.add_rect(METAL1, offset=z_pin.rc(), width=a_pin.lx() - z_pin.rx())

    def connect_z_to_b(self, z_inst, b_inst, b_name="B", z_name="Z"):
        b_pin = b_inst.get_pin(b_name)
        z_pin = z_inst.get_pin(z_name)
        self.add_rect(METAL2, offset=vector(z_pin.cx(), z_pin.cy() - 0.5 * self.m1_width),
                      width=b_pin.cx() - z_pin.rx())
        self.add_contact_center(m1m2.layer_stack, offset=z_pin.center())
        self.add_contact_center(m1m2.layer_stack, offset=vector(b_pin.cx(), z_pin.cy()))

    def add_output_pins(self):
        pin_names = ["clk_buf", "clk_bar", "wordline_en", "precharge_en_bar",
                     "write_en", "sense_en", "tri_en", "sample_bar", ]
        mod_names = ["out_inv", "out", "out", "out", "out_inv", "out_inv", "out_inv", "out"]
        instances = [self.clk_buf_inst, self.clk_buf_inst, self.wordline_buf_inst,
                     self.precharge_buf_inst, self.write_buf_inst, self.sense_amp_buf_inst,
                     self.tri_en_buf_inst, self.sample_bar_inst]
        for i in range(len(pin_names)):
            if not instances[i]:
                continue
            out_pin = instances[i].get_pin(mod_names[i])
            if out_pin.cy() > self.mid_y:
                via_offset = out_pin.ul() - vector(0, m1m2.height)
                self.add_layout_pin(pin_names[i], "metal2", offset=out_pin.ul(),
                                    height=self.height - out_pin.uy())
            else:
                self.add_layout_pin(pin_names[i], "metal2", offset=vector(out_pin.lx(), 0),
                                    height=out_pin.by())
                via_offset = out_pin.ll()
            self.add_contact(m1m2.layer_stack, offset=via_offset)

    def add_power_pins(self):
        for pin_name in ["vdd", "gnd"]:
            for inst in [self.clk_buf_inst, self.tri_en_buf_inst]:
                pin = inst.get_pin(pin_name)
                self.add_layout_pin(pin_name, pin.layer, offset=vector(0, pin.by()),
                                    height=pin.height(), width=self.width)


class LeftLatchedControlLogic(LatchedControlLogic):
    def add_pin_list(self, pin_list, pin_type_list=None):
        pin_list.remove("wordline_en")
        super().add_pin_list(pin_list)
