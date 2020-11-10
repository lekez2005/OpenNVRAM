from base.contact import cross_m2m3, m1m2
from base.design import METAL2, METAL3, METAL1
from base.hierarchy_layout import GDS_ROT_270
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

    def add_pins(self):
        self.add_pin_list(["bank_sel", "read", "clk", "sense_trig", "precharge_trig",
                           "clk_buf", "clk_bar", "wordline_en", "precharge_en_bar",
                           "write_en", "sense_en", "tri_en", "sample_bar", "vdd", "gnd"])

    def get_num_rails(self):
        return 5

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

        assert len(OPTS.tri_en_buffers) % 2 == 1, "Number of sense_en buffers should be odd"
        self.tri_en_buf = BufferStagesHorizontal(OPTS.tri_en_buffers)
        self.add_mod(self.tri_en_buf)

    def add_modules(self):
        y_offset = self.rail_pos[-1] + self.bus_pitch + 0.5 * self.rail_height

        self.clk_buf_inst = self.add_inst("clk_buf", mod=self.clk_buf,
                                          offset=vector(0, y_offset))
        self.connect_inst(["bank_sel", "clk", "clk_buf", "clk_bar", "vdd", "gnd"])

        self.precharge_buf_inst = self.add_inst("precharge_buf", mod=self.precharge_buf,
                                                offset=self.clk_buf_inst.lr())
        self.connect_inst(["bank_sel", "precharge_trig", "precharge_en",
                           "precharge_en_bar", "vdd", "gnd"])

        self.sel_trig_inst = self.add_inst("sel_trig", mod=self.nand2,
                                           offset=self.precharge_buf_inst.lr())
        self.connect_inst(["bank_sel", "sense_trig", "sel_trig_bar", "vdd", "gnd"])

        self.body_tap_inst = self.add_inst(self.body_tap.name, mod=self.body_tap,
                                           offset=self.sel_trig_inst.lr())
        self.connect_inst([])

        self.clk_bar_inst = self.add_inst("clk_bar", mod=self.inv, offset=self.body_tap_inst.lr())
        self.connect_inst(["clk", "clk_bar_int", "vdd", "gnd"])

        self.bank_sel_cbar_inst = self.add_inst("bank_sel_cbar", mod=self.nand2,
                                                offset=self.clk_bar_inst.lr())
        self.connect_inst(["bank_sel", "clk_bar_int", "bank_sel_cbar", "vdd", "gnd"])

        self.wordline_buf_inst = self.add_inst("wordline_buf", mod=self.wordline_buf,
                                               offset=self.bank_sel_cbar_inst.lr())
        self.connect_inst(["sense_trig", "bank_sel_cbar",
                           "wordline_en_bar", "wordline_en", "vdd", "gnd"])

        self.write_buf_inst = self.add_inst("write_buf", mod=self.write_buf,
                                            offset=self.wordline_buf_inst.lr())
        self.connect_inst(["read", "bank_sel_cbar", "write_en", "write_en_bar", "vdd", "gnd"])

        self.sel_cbar_trig_inst = self.add_inst("sel_cbar_trig", mod=self.nor2,
                                                offset=self.write_buf_inst.lr())
        self.connect_inst(["sense_trig", "bank_sel_cbar", "sel_cbar_trig", "vdd", "gnd"])

        self.sample_bar_inst = self.add_inst("sample_bar", mod=self.sample_bar,
                                             offset=self.sel_cbar_trig_inst.lr())
        self.connect_inst(["read", "sel_cbar_trig", "sample_en_buf", "sample_bar", "vdd", "gnd"])

        self.body_tap_inst2 = self.add_inst(self.body_tap.name, mod=self.body_tap,
                                            offset=self.sample_bar_inst.lr())
        self.connect_inst([])

        self.sense_amp_buf_inst = self.add_inst("sense_amp_buf", mod=self.sense_amp_buf,
                                                offset=self.body_tap_inst2.lr())
        self.connect_inst(["sel_trig_bar", "sense_en", "sense_en_bar", "vdd", "gnd"])

        self.tri_en_buf_inst = self.add_inst("tri_en_buf", mod=self.tri_en_buf,
                                             offset=self.sense_amp_buf_inst.lr())
        self.connect_inst(["sel_trig_bar", "tri_en", "tri_en_bar", "vdd", "gnd"])

    def add_input_pins(self):
        def get_pin_x(inst, pin_name="A"):
            pin = inst.get_pin(pin_name)
            return pin.cx() + 0.5 * max(cross_m2m3.width, cross_m2m3.height)

        self.bank_sel_pin = self.add_layout_pin("bank_sel", "metal3", height=self.bus_width,
                                                offset=vector(0, self.rail_pos[4]),
                                                width=get_pin_x(self.bank_sel_cbar_inst))

        self.clk_pin = self.add_layout_pin("clk", "metal3", offset=vector(0, self.rail_pos[3]),
                                           height=self.bus_width,
                                           width=get_pin_x(self.clk_bar_inst))

        self.read_pin = self.add_layout_pin("read", "metal3", offset=vector(0, self.rail_pos[2]),
                                            height=self.bus_width,
                                            width=get_pin_x(self.sample_bar_inst))

        self.sense_trig_pin = self.add_layout_pin("sense_trig", "metal3",
                                                  offset=vector(0, self.rail_pos[1]),
                                                  height=self.bus_width,
                                                  width=get_pin_x(self.sel_cbar_trig_inst))

        self.precharge_trig_pin = self.add_layout_pin("precharge_trig", "metal3",
                                                      offset=vector(0, self.rail_pos[0]),
                                                      height=self.bus_width,
                                                      width=get_pin_x(self.precharge_buf_inst, "B"))

    def route_internal_signals(self):
        self.connect_pin_to_rail(self.clk_buf_inst, "A", self.bank_sel_pin)
        self.connect_pin_to_rail(self.clk_buf_inst, "B", self.clk_pin)

        self.connect_pin_to_rail(self.precharge_buf_inst, "A", self.bank_sel_pin)
        self.connect_pin_to_rail(self.precharge_buf_inst, "B", self.precharge_trig_pin)

        self.connect_pin_to_rail(self.sel_trig_inst, "A", self.bank_sel_pin)
        self.connect_pin_to_rail(self.sel_trig_inst, "B", self.sense_trig_pin)

        via_extension = 0.5 * max(cross_m2m3.width, cross_m2m3.height)
        rail_x = self.sel_trig_inst.get_pin("Z").cx() - via_extension
        self.sel_trig_rail = \
            self.add_rect(METAL3, offset=vector(rail_x, self.precharge_trig_pin.by()),
                          width=self.tri_en_buf_inst.get_pin("in").cx() - rail_x + via_extension,
                          height=self.bus_width)
        self.connect_pin_to_rail(self.sel_trig_inst, "Z", self.sel_trig_rail)

        self.connect_pin_to_rail(self.clk_bar_inst, "A", self.clk_pin)

        self.connect_z_to_b(z_inst=self.clk_bar_inst, b_inst=self.bank_sel_cbar_inst)
        self.connect_pin_to_rail(self.bank_sel_cbar_inst, "A", self.bank_sel_pin)

        rail_x = self.bank_sel_cbar_inst.get_pin("Z").cx() - via_extension
        self.bank_sel_cbar_rail = \
            self.add_rect(METAL3, offset=vector(rail_x, self.bank_sel_pin.by()),
                          width=self.sel_cbar_trig_inst.get_pin("B").cx() - rail_x + via_extension,
                          height=self.bus_width)
        self.connect_pin_to_rail(self.bank_sel_cbar_inst, "Z", self.bank_sel_cbar_rail)

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

    def connect_pin_to_rail(self, inst, pin_name, rail):
        pin = inst.get_pin(pin_name)
        self.add_cross_contact_center(cross_m2m3, vector(pin.cx(), rail.cy()))
        self.add_rect(METAL2, offset=vector(pin.cx() - 0.5 * self.m2_width, rail.cy()),
                      height=pin.by() - rail.cy(), width=self.m2_width)
        self.add_contact(m1m2.layer_stack, offset=vector(pin.cx() - 0.5 * self.m2_width,
                                                         pin.by()))

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
            out_pin = instances[i].get_pin(mod_names[i])
            self.add_layout_pin(pin_names[i], "metal2", offset=out_pin.ul(),
                                height=self.height - out_pin.uy())
            self.add_contact(m1m2.layer_stack, offset=out_pin.ul() - vector(0, m1m2.height))

    def add_power_pins(self):
        for pin_name in ["vdd", "gnd"]:
            pin = self.clk_buf_inst.get_pin(pin_name)
            self.add_layout_pin(pin_name, pin.layer, offset=vector(0, pin.by()),
                                height=pin.height(), width=self.width)
