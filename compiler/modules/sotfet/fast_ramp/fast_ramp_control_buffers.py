from base.contact import m2m3, m1m2
from base.design import METAL2, METAL1
from base.vector import vector
from globals import OPTS
from modules.logic_buffer import LogicBuffer
from modules.sotfet.sf_control_buffers import SfControlBuffers
from pgates.pinv import pinv


class FastRampControlBuffers(SfControlBuffers):
    """
    Quick hack for very thin bitcell array. Too hacky to be reusable
    """
    inv2 = None

    def create_layout(self):
        super().create_layout()
        self.offset_all_coordinates()
        self.height = self.clk_sel_inst.uy()

    def get_num_rails(self):
        return 5

    def create_modules(self):
        super().create_modules()
        self.inv2 = pinv(size=2, **self.get_common_args())
        self.add_mod(self.inv2)

    def create_wordline_en(self):
        assert len(OPTS.wordline_en_buffers) % 2 == 1, "Number of wordline buffers should be odd"
        self.wordline_buf = LogicBuffer(buffer_stages=OPTS.wordline_en_buffers, logic="pnand3",
                                        **self.get_logic_args())
        self.add_mod(self.wordline_buf)

    def create_sense_amp_en(self):
        assert len(OPTS.sense_amp_buffers) % 2 == 1, "Number of sense_amp buffers should be odd"
        self.sense_amp_buf = LogicBuffer(buffer_stages=OPTS.sense_amp_buffers, logic="pnand3",
                                         **self.get_logic_args())
        self.add_mod(self.sense_amp_buf)

    def add_input_pins(self):
        self.bank_sel_pin = self.add_layout_pin("bank_sel", "metal3",
                                                offset=vector(0, self.rail_pos[3]),
                                                width=self.sense_amp_buf_inst.get_pin("A").cx())
        self.search_pin = self.add_layout_pin("search", "metal3",
                                              offset=vector(0, self.rail_pos[2]),
                                              width=self.sense_amp_buf_inst.get_pin("A").lx())
        self.clk_pin = self.add_layout_pin("clk", "metal3", offset=vector(0, self.rail_pos[1]),
                                           width=self.clk_bar_inst.get_pin("A").cx())

    def add_modules(self):
        y_offset = self.rail_pos[-1] + self.m3_width + 0.5 * self.rail_height

        self.clk_sel_inst = self.add_inst("clk_sel", mod=self.nand, offset=vector(0, y_offset))
        self.connect_inst(["bank_sel", "clk", "clk_sel_bar", "vdd", "gnd"])

        self.clk_buf_inst = self.add_inst("clk_buf", mod=self.clk_buf, offset=self.clk_sel_inst.lr())
        self.connect_inst(["clk_sel_bar", "clk_buf", "clk_bar", "vdd", "gnd"])

        self.clk_bar_inst = self.add_inst("clk_bar_int", mod=self.inv2, offset=self.clk_buf_inst.lr())
        self.connect_inst(["clk", "clk_bar_int", "vdd", "gnd"])

        self.bitline_en_inst = self.add_inst("bitline_en", mod=self.bitline_en, offset=self.clk_bar_inst.lr())
        self.connect_inst(["bank_sel", "clk_bar_int", "bitline_en", "bitline_en_bar", "vdd", "gnd"])

        self.sense_amp_buf_inst = self.add_inst("sense_amp_buf", mod=self.sense_amp_buf,
                                                offset=self.bitline_en_inst.lr())
        self.connect_inst(["bank_sel", "search", "clk_bar_int", "sense_amp_en", "sense_amp_bar", "vdd", "gnd"])

        # split here
        y_offset = self.rail_pos[0] - self.m3_width - 0.5 * self.rail_height - self.inv.height
        x_offset = 0

        self.search_bar_inst = self.add_inst("search_bar", mod=self.inv,
                                             offset=vector(x_offset, y_offset))
        self.connect_inst(["search", "search_bar", "vdd", "gnd"])

        self.wordline_buf_inst = self.add_inst("wordline_en", mod=self.wordline_buf, offset=self.search_bar_inst.lr())
        self.connect_inst(["search_bar", "bank_sel", "clk_bar_int",
                           "wordline_en", "wordline_bar", "vdd", "gnd"])

        self.chb_buf_inst = self.add_inst("chb", mod=self.chb_buf, offset=self.wordline_buf_inst.lr())
        self.connect_inst(["search_bar", "clk_sel_bar", "precharge_en_bar", "precharge_en", "vdd", "gnd"])

    def route_internal_signals(self):
        self.connect_a_pin(self.clk_sel_inst, self.bank_sel_pin, via_dir="right")
        self.connect_b_pin(self.clk_sel_inst, self.clk_pin, via_dir="left")

        self.connect_z_to_a(self.clk_sel_inst, self.clk_buf_inst, a_name="in")

        clk_sel_bar_rail = self.create_output_rail(self.clk_sel_inst.get_pin("Z"), self.rail_pos[4],
                                                   self.chb_buf_inst.get_pin("A"))

        self.connect_inverter_in(self.clk_bar_inst, self.clk_pin)

        clk_bar_rail = self.create_output_rail(self.clk_bar_inst.get_pin("Z"), self.clk_pin,
                                               self.sense_amp_buf_inst.get_pin("C"))

        self.connect_z_to_b(self.clk_bar_inst.get_pin("Z"), self.bitline_en_inst.get_pin("B"))
        self.connect_a_pin(self.bitline_en_inst, self.bank_sel_pin, via_dir="left")

        self.connect_a_pin(self.sense_amp_buf_inst, self.bank_sel_pin)
        self.connect_b_pin(self.sense_amp_buf_inst, self.search_pin, via_dir="left")
        self.connect_c_pin(self.sense_amp_buf_inst, clk_bar_rail)

        a_pin = self.search_bar_inst.get_pin("A")
        rail = self.search_pin
        self.add_rect("metal2", offset=vector(a_pin.lx(), a_pin.cy()),
                      height=rail.cy() - a_pin.cy())

        x_offset = a_pin.lx() + m2m3.height
        self.add_rect(METAL2, offset=vector(a_pin.lx(), rail.by()),
                      width=x_offset - a_pin.lx())

        self.add_contact(m2m3.layer_stack, offset=vector(x_offset + m2m3.height, rail.by()),
                         rotate=90)
        self.add_contact(m1m2.layer_stack, offset=vector(a_pin.lx(),
                                                         a_pin.cy() - 0.5 * m1m2.height))

        search_bar_rail = self.create_output_rail(self.search_bar_inst.get_pin("Z"),
                                                  self.rail_pos[0],
                                                  self.chb_buf_inst.get_pin("A"),
                                                  via_dir="left")
        # wordline buf

        a_pin = self.wordline_buf_inst.get_pin("A")
        b_pin = self.wordline_buf_inst.get_pin("B")
        c_pin = self.wordline_buf_inst.get_pin("C")

        z_pin = self.search_bar_inst.get_pin("Z")

        self.add_rect(METAL1, offset=vector(z_pin.lx(), a_pin.by()),
                      width=a_pin.lx() - z_pin.lx())

        x_offset = z_pin.rx() + self.get_parallel_space(METAL2)
        self.add_rect(METAL2, offset=vector(x_offset, b_pin.cy()),
                      height=self.bank_sel_pin.uy() - b_pin.cy())
        self.add_contact(m2m3.layer_stack, offset=vector(x_offset,
                                                         self.bank_sel_pin.by()),
                         rotate=90)
        self.add_rect(METAL2, offset=vector(x_offset, b_pin.by()),
                      width=b_pin.cx() - x_offset)
        self.add_contact_center(m1m2.layer_stack, offset=b_pin.center())

        x_offset += self.get_parallel_space(METAL2) + self.m2_space

        self.add_rect(METAL2, offset=vector(x_offset, c_pin.by()),
                      height=clk_bar_rail.uy() - c_pin.by())
        self.add_contact(m1m2.layer_stack, offset=vector(x_offset + m1m2.height,
                                                         clk_bar_rail.uy()),
                         rotate=90)
        self.add_rect(METAL1, offset=vector(x_offset, clk_bar_rail.uy()),
                      width=clk_bar_rail.lx() - x_offset + m1m2.height)
        self.add_contact(m1m2.layer_stack, offset=vector(clk_bar_rail.lx() + m1m2.height,
                                                         clk_bar_rail.uy()), rotate=90)
        self.add_rect(METAL2, offset=vector(x_offset, c_pin.by()),
                      width=c_pin.cx() - x_offset)
        self.add_contact(m1m2.layer_stack, offset=vector(c_pin.lx(), c_pin.uy() - m1m2.height))

        # chb_buf
        a_pin = self.chb_buf_inst.get_pin("A")
        b_pin = self.chb_buf_inst.get_pin("B")

        x_offset = a_pin.lx() + self.m1_width - m1m2.height
        self.add_rect(METAL2, offset=vector(x_offset, b_pin.by()),
                      height=search_bar_rail.uy() - b_pin.by())
        self.add_contact(m1m2.layer_stack, offset=vector(x_offset + m1m2.height, b_pin.by()),
                         rotate=90)
        self.add_contact(m2m3.layer_stack, offset=vector(x_offset + m2m3.height,
                                                         search_bar_rail.by()),
                         rotate=90)

        x_offset -= (self.m2_width + self.get_parallel_space(METAL2))
        offset = vector(x_offset, a_pin.by())
        self.add_rect(METAL2, offset=offset, height=clk_sel_bar_rail.uy() - a_pin.by())
        self.add_rect(METAL2, offset=offset, width=b_pin.cx() - x_offset)
        self.add_contact(m1m2.layer_stack, offset=vector(b_pin.lx(), a_pin.by()))
        self.add_contact(m2m3.layer_stack, offset=vector(x_offset+m2m3.height,
                                                         clk_sel_bar_rail.by()),
                         rotate=90)

    def add_output_pins(self):
        pin_names = ["clk_buf", "bitline_en", "sense_amp_en", "wordline_en", "precharge_en_bar"]
        mod_names = ["out_inv", "out_inv", "out_inv", "out_inv", "out_inv"]
        instances = [self.clk_buf_inst, self.bitline_en_inst, self.sense_amp_buf_inst,
                     self.wordline_buf_inst, self.chb_buf_inst]
        for i in range(5):
            out_pin = instances[i].get_pin(mod_names[i])
            if i >= 3:
                self.add_layout_pin(pin_names[i], METAL2,
                                    offset=vector(out_pin.lx(), self.wordline_buf_inst.by()),
                                    height=out_pin.by() - self.wordline_buf_inst.by())
            else:
                self.add_layout_pin(pin_names[i], "metal2", offset=out_pin.ul(),
                                    height=self.height - out_pin.uy())

    def add_power_pins(self):
        for inst in [self.clk_sel_inst, self.chb_buf_inst]:
            for pin_name in ["vdd", "gnd"]:
                pin = inst.get_pin(pin_name)
                self.add_layout_pin(pin_name, layer=pin.layer,
                                    offset=vector(0, pin.by()), width=self.width,
                                    height=pin.height())
