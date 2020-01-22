import debug
from base import design
from base.contact import m1m2, m2m3
from base.vector import vector
from globals import OPTS
from modules.buffer_stage import BufferStage
from modules.logic_buffer import LogicBuffer
from pgates.pinv import pinv
from pgates.pnand2 import pnand2


class ControlBuffers(design.design):
    """
    Generate and buffer control signals using bank_sel, clk and read
    Assumes write if read_bar, bitline computation vs read difference is handled at decoder level
    Inputs:
        bank_sel, read, clk
    Define internal signal
        bank_sel_cbar = clk_bar.bank_sel
    Outputs
        wordline_en: bank_sel_cbar
        clk_buf:     clk_bank_sel_bar
        precharge_en_bar: and3(read, read, bank_sel)
        write_en:     bank_sel_cbar.read_bar
        sense_en: bank_sel_cbar.read (same as tri_en)
        tri_en_bar: sense_en_bar
    """
    name = "control_buffers"

    nand = inv = clk_buf = write_buf = sense_amp_buf = wordline_buf = precharge_buf = None
    clk_bar_inst = bank_sel_cbar_inst = read_bar_inst = None
    clk_buf_inst = write_buf_inst = sense_amp_buf_inst = wordline_buf_inst = precharge_buf_inst = None

    bank_sel_pin = clk_pin = read_pin = sel_cbar_rail = None

    def __init__(self, contact_nwell=True, contact_pwell=True):
        design.design.__init__(self, self.name)
        debug.info(2, "Create Logic Buffers gate")

        self.logic_heights = OPTS.logic_buffers_height
        self.contact_pwell = contact_pwell
        self.contact_nwell = contact_nwell

        self.rail_pos = [0.0] * self.get_num_rails()

        self.create_layout()

    def get_num_rails(self):
        return 4

    def create_layout(self):
        self.add_pins()
        self.create_modules()
        self.calculate_rail_positions()
        self.add_modules()

        rightmost_module = max(filter(lambda x: hasattr(x.mod, "pins") and len(x.mod.pins) > 0, self.insts),
                               key=lambda x: x.rx())
        self.width = rightmost_module.rx()

        self.add_input_pins()
        self.route_internal_signals()

        self.add_output_pins()
        self.add_power_pins()

    def get_common_args(self):
        return {
            'height': self.logic_heights,
            'contact_nwell': self.contact_nwell,
            'contact_pwell': self.contact_pwell,
        }

    def get_buffer_args(self):
        args = self.get_common_args()
        args.update(route_outputs=False)
        return args

    def get_logic_args(self):
        args = self.get_buffer_args()
        args.update(route_inputs=False)
        return args

    def create_modules(self):

        self.nand = pnand2(**self.get_common_args())
        self.add_mod(self.nand)

        self.inv = pinv(**self.get_common_args())
        self.add_mod(self.inv)

        self.clk_buf = LogicBuffer(buffer_stages=OPTS.clk_buffers, logic="pnand2", **self.get_logic_args())
        self.add_mod(self.clk_buf)

        assert len(OPTS.wordline_en_buffers) % 2 == 1, "Number of wordline buffers should be odd"
        self.wordline_buf = BufferStage(buffer_stages=OPTS.wordline_en_buffers, **self.get_buffer_args())
        self.add_mod(self.wordline_buf)

        self.write_buf = LogicBuffer(buffer_stages=OPTS.write_buffers, logic="pnor2", **self.get_logic_args())
        self.add_mod(self.write_buf)

        self.sense_amp_buf = LogicBuffer(buffer_stages=OPTS.sense_amp_buffers, logic="pnor2", **self.get_logic_args())
        self.add_mod(self.sense_amp_buf)

        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        self.precharge_buf = LogicBuffer(buffer_stages=OPTS.precharge_buffers, logic="pnand3", **self.get_logic_args())
        self.add_mod(self.precharge_buf)

    def add_modules(self):
        y_offset = self.rail_pos[-1] + self.m3_width - 0.5*self.rail_height

        self.precharge_buf_inst = self.add_inst("precharge_buf", mod=self.precharge_buf,
                                                offset=vector(0, y_offset))
        self.connect_inst(["read", "bank_sel", "clk", "precharge_en", "precharge_en_bar", "vdd", "gnd"])

        self.clk_buf_inst = self.add_inst("clk_buf", mod=self.clk_buf, offset=self.precharge_buf_inst.lr())
        self.connect_inst(["bank_sel", "clk", "clk_buf", "clk_bar", "vdd", "gnd"])

        self.clk_bar_inst = self.add_inst("clk_bar", mod=self.inv, offset=self.clk_buf_inst.lr())
        self.connect_inst(["clk", "clk_bar_int", "vdd", "gnd"])

        self.bank_sel_cbar_inst = self.add_inst("bank_sel_cbar", mod=self.nand, offset=self.clk_bar_inst.lr())
        self.connect_inst(["bank_sel", "clk_bar_int", "bank_sel_cbar", "vdd", "gnd"])

        self.wordline_buf_inst = self.add_inst("wordline_buf", mod=self.wordline_buf,
                                               offset=self.bank_sel_cbar_inst.lr())
        self.connect_inst(["bank_sel_cbar", "wordline_en", "wordline_en_bar", "vdd", "gnd"])

        self.write_buf_inst = self.add_inst("write_buf", mod=self.write_buf, offset=self.wordline_buf_inst.lr())
        self.connect_inst(["bank_sel_cbar", "read", "write_en_bar", "write_en", "vdd", "gnd"])

        self.read_bar_inst = self.add_inst("read_bar", mod=self.inv, offset=self.write_buf_inst.lr())
        self.connect_inst(["read", "read_bar", "vdd", "gnd"])

        self.sense_amp_buf_inst = self.add_inst("sense_amp_buf", mod=self.sense_amp_buf,
                                                offset=self.read_bar_inst.lr())
        self.connect_inst(["bank_sel_cbar", "read_bar", "sense_en_bar", "sense_en", "vdd", "gnd"])

    def calculate_rail_positions(self):
        for i in range(len(self.rail_pos)):
            self.rail_pos[i] = i * (self.m3_width + self.parallel_line_space)

        self.height = self.rail_pos[-1] + self.m3_width + 0.5*self.rail_height + self.logic_heights

    def add_input_pins(self):

        self.clk_pin = self.add_layout_pin("clk", "metal3", offset=vector(0, self.rail_pos[2]),
                                           width=self.clk_bar_inst.get_pin("A").cx())

        self.read_pin = self.add_layout_pin("read", "metal3", offset=vector(0, self.rail_pos[0]),
                                            width=self.read_bar_inst.get_pin("A").cx())

        self.bank_sel_pin = self.add_layout_pin("bank_sel", "metal3", offset=vector(0, self.rail_pos[1]),
                                                width=self.bank_sel_cbar_inst.get_pin("B").cx())

    def connect_inverter_in(self, inst, rail, pin_name="A"):
        pin = inst.get_pin(pin_name)
        self.add_rect("metal2", offset=vector(pin.lx(), rail.by()), height=pin.cy() - rail.by())
        self.add_contact(m2m3.layer_stack, offset=vector(pin.lx() + m2m3.height, rail.by()),
                         rotate=90)
        self.add_contact(m1m2.layer_stack, offset=vector(pin.lx(), pin.cy() - 0.5 * m1m2.height))

    def connect_a_pin(self, inst, rail, via_dir="right"):
        pin = inst.get_pin("A")
        x_offset = pin.rx() - m1m2.height
        if via_dir == "right":
            via_x = x_offset + m2m3.height
        else:
            via_x = x_offset + self.m2_width
        self.add_contact(m2m3.layer_stack, offset=vector(via_x, rail.by()), rotate=90)
        self.add_rect("metal2", offset=vector(x_offset, rail.by()), height=pin.cy() - rail.by())
        self.add_contact(m1m2.layer_stack, offset=vector(x_offset + m1m2.height, pin.cy() - 0.5 * m1m2.width),
                         rotate=90)

    def connect_b_pin(self, inst, rail, via_dir="right"):
        pin = inst.get_pin("B")
        x_offset = inst.get_pin("A").rx() - m1m2.height - self.parallel_line_space - self.m2_width
        if via_dir == "right":
            via_x = x_offset + m2m3.height
        else:
            via_x = x_offset + self.m2_width
        self.add_contact(m2m3.layer_stack, offset=vector(via_x, rail.by()), rotate=90)
        self.add_rect("metal2", offset=vector(x_offset, rail.by()), height=pin.cy() - rail.by())
        self.add_rect("metal2", offset=vector(x_offset, pin.cy() - 0.5 * self.m2_width),
                      width=pin.lx() - x_offset)
        self.add_contact_center(m1m2.layer_stack, offset=pin.center())

    def connect_c_pin(self, inst, rail, via_dir="right"):
        c_pin = inst.get_pin("C")
        b_pin = inst.get_pin("B")
        a_pin = inst.get_pin("A")
        x_offset = b_pin.lx()
        if via_dir == "right":
            via_x = x_offset + m2m3.height
        else:
            via_x = x_offset + self.m2_width
        self.add_contact(m2m3.layer_stack, offset=vector(via_x, rail.by()), rotate=90)
        self.add_rect("metal2", offset=vector(x_offset, rail.by()), height=a_pin.uy() - rail.by())
        self.add_rect("metal2", offset=vector(x_offset, a_pin.uy()-self.m2_width),
                      width=c_pin.lx()-x_offset)
        self.add_contact(m1m2.layer_stack, offset=vector(c_pin.lx(), a_pin.uy() - 0.5 * m1m2.height))

    def create_output_rail(self, output_pin, existing_rail, destination_pin):
        if not isinstance(existing_rail, float):
            existing_rail = existing_rail.by()
        rail = self.add_rect("metal3", offset=vector(output_pin.lx(), existing_rail),
                             width=destination_pin.lx() - output_pin.lx())
        self.add_rect("metal2", offset=vector(output_pin.lx(), rail.by()),
                      height=output_pin.by() - rail.by())
        self.add_contact(m2m3.layer_stack, offset=vector(output_pin.lx() + m2m3.height, rail.by()), rotate=90)
        return rail

    def connect_z_to_b(self, z_pin, b_pin):
        y_offset = b_pin.cy() - 0.5 * self.m2_width
        self.add_rect("metal2", offset=vector(z_pin.lx(), y_offset), height=z_pin.uy() - y_offset)
        self.add_rect("metal2", offset=vector(z_pin.lx(), y_offset), width=b_pin.lx() - z_pin.lx())
        self.add_contact_center(m1m2.layer_stack, b_pin.center())

    def connect_z_to_a(self, z_inst, a_inst, a_name="A"):
        a_pin = a_inst.get_pin(a_name)
        z_pin = z_inst.get_pin("Z")
        self.add_rect("metal1", offset=vector(z_pin.rx(), a_pin.cy() - 0.5*self.m1_width),
                      width=a_pin.lx()-z_pin.rx())

    def route_internal_signals(self):

        # route precharge_buf_inst
        a_pin = self.precharge_buf_inst.get_pin("A")
        source_pin = self.read_pin
        self.add_rect("metal2", offset=vector(a_pin.lx(), source_pin.by()),
                      height=a_pin.cy() - source_pin.by())
        self.add_contact_center(m1m2.layer_stack, offset=a_pin.center())
        self.add_contact(m2m3.layer_stack, offset=vector(a_pin.lx() + m2m3.height, source_pin.by()),
                         rotate=90)

        b_pin = self.precharge_buf_inst.get_pin("B")
        source_pin = self.bank_sel_pin
        self.add_rect("metal2", offset=vector(b_pin.lx(), source_pin.by()),
                      height=b_pin.cy() - source_pin.by())
        self.add_contact_center(m1m2.layer_stack, offset=b_pin.center())
        self.add_contact(m2m3.layer_stack, offset=vector(b_pin.lx() + m2m3.height, source_pin.by()),
                         rotate=90)

        c_pin = self.precharge_buf_inst.get_pin("C")

        x_offset = a_pin.lx() - self.parallel_line_space - self.m2_width
        self.add_contact(m2m3.layer_stack, offset=vector(x_offset+self.m2_width, self.clk_pin.by()),
                         rotate=90)
        self.add_rect("metal2", offset=vector(x_offset, self.clk_pin.by()), height=c_pin.cy()-self.clk_pin.by())
        self.add_rect("metal2", offset=vector(x_offset, c_pin.cy()-0.5*self.m2_width),
                      width=c_pin.lx()-x_offset)

        self.add_contact(m1m2.layer_stack, offset=vector(c_pin.lx(), c_pin.uy() - m1m2.height))

        # clk_buf

        # connect clk_buf input
        # connect_inverter_in(self.clk_buf_inst, self.sel_cbar_rail, "in")
        self.connect_a_pin(self.clk_buf_inst, self.bank_sel_pin, via_dir="left")
        self.connect_b_pin(self.clk_buf_inst, self.clk_pin, via_dir="left")

        self.connect_inverter_in(self.clk_bar_inst, self.clk_pin)

        self.connect_a_pin(self.bank_sel_cbar_inst, self.bank_sel_pin)
        # output of clk_bar to bank_sel_cbar_inst
        self.connect_z_to_b(self.clk_bar_inst.get_pin("Z"), self.bank_sel_cbar_inst.get_pin("B"))

        # bank_sel_cbar_inst output
        self.add_sel_cbar_rail()
        z_pin = self.bank_sel_cbar_inst.get_pin("Z")
        self.add_rect("metal2", offset=vector(z_pin.lx(), self.clk_pin.by()), height=z_pin.by()-self.clk_pin.by())

        self.add_contact(m2m3.layer_stack, offset=vector(z_pin.lx()+m2m3.height, self.sel_cbar_rail.by()),
                         rotate=90)

        # connect to wordline en
        a_pin = self.wordline_buf_inst.get_pin("in")
        self.add_rect("metal1", offset=vector(z_pin.lx(), a_pin.cy()-0.5*self.m1_width),
                      width=a_pin.lx()-z_pin.lx())

        # write buf
        self.connect_a_pin(self.write_buf_inst, self.sel_cbar_rail)
        self.connect_b_pin(self.write_buf_inst, self.read_pin)

        # read bar
        self.connect_inverter_in(self.read_bar_inst, self.read_pin)

        # sense amp
        self.route_sense_amp()

    def add_sel_cbar_rail(self):
        z_pin = self.bank_sel_cbar_inst.get_pin("Z")
        self.sel_cbar_rail = self.add_rect("metal3", offset=vector(z_pin.lx(), self.clk_pin.by()),
                                           width=self.sense_amp_buf_inst.get_pin("B").lx() - z_pin.lx())

    def route_sense_amp(self):
        self.connect_a_pin(self.sense_amp_buf_inst, self.sel_cbar_rail)
        self.connect_z_to_b(self.read_bar_inst.get_pin("Z"), self.sense_amp_buf_inst.get_pin("B"))

    def add_output_pins(self):
        pin_names = ["precharge_en_bar", "clk_buf", "clk_bar", "wordline_en", "write_en", "write_en_bar",
                     "sense_en", "sense_en_bar"]
        mod_names = ["out", "out_inv", "out", "out_inv", "out", "out_inv", "out", "out_inv"]
        instances = [self.precharge_buf_inst, self.clk_buf_inst, self.clk_buf_inst, self.wordline_buf_inst,
                     self.write_buf_inst, self.write_buf_inst, self.sense_amp_buf_inst, self.sense_amp_buf_inst]
        for i in range(len(pin_names)):
            out_pin = instances[i].get_pin(mod_names[i])
            self.add_layout_pin(pin_names[i], "metal2", offset=out_pin.ul(), height=self.height-out_pin.uy())

    def add_power_pins(self):
        sense_amp_gnd = self.sense_amp_buf_inst.get_pin("gnd")
        self.add_layout_pin("gnd", "metal1", offset=vector(0, sense_amp_gnd.by()), width=self.width,
                            height=sense_amp_gnd.height())
        sense_amp_vdd = self.sense_amp_buf_inst.get_pin("vdd")
        self.add_layout_pin("vdd", "metal1", offset=vector(0, sense_amp_vdd.by()), width=self.width,
                            height=sense_amp_vdd.height())

    def add_pins(self):
        self.add_pin_list(["bank_sel", "read", "clk", "clk_buf", "clk_bar", "wordline_en", "precharge_en_bar", "write_en",
                           "write_en_bar", "sense_en", "sense_en_bar", "vdd", "gnd"])
