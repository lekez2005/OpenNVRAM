from base.contact import m2m3
from base.vector import vector
from globals import OPTS
from modules.buffer_stage import BufferStage
from modules.control_buffers import ControlBuffers
from modules.logic_buffer import LogicBuffer
from pgates.pinv import pinv
from pgates.pnand2 import pnand2


class SfControlBuffers(ControlBuffers):
    """
    Generate and buffer control signals using bank_sel, clk and search pins
    define clk_search_bar = NAND(clk, search)
           clk_sel_bar = NAND(bank_sel, clk)

    clk_buf = bank_sel.clk
    bitline_en = bank_sel.(clk_bar + search_bar)
        = AND(bank_sel, OR(clk_bar, search_bar)
        = AND(bank_sel, NAND(clk, bar)
        = AND(bank_sel, clk_search_bar)
    wordline_en = bank_sel.clk.search_bar
        = AND(search_bar, AND(bank_sel, clk))
        = NOR(search, NAND(bank_sel, clk))
    precharge_en_bar = bank_sel.clk.search
        = NOR(search_bar, NAND(clk, search)
        = NOR(search_bar, clk_search_bar)
    sense_amp_en = bank_sel.clk_bar.search
        = NOR(clk, NAND(bank_sel, search))
    """

    nor = nand3 = bitline_en = chb_buf = None
    clk_sel_inst = search_bar_inst = sel_search_bar_inst = bitline_en_inst = chb_buf_inst = None
    clk_search_inst_bar = None

    search_pin = None

    def create_modules(self):
        self.nand = pnand2(**self.get_common_args())
        self.add_mod(self.nand)

        self.inv = pinv(**self.get_common_args())
        self.add_mod(self.inv)

        self.clk_buf = BufferStage(buffer_stages=OPTS.clk_buffers, **self.get_buffer_args())
        self.add_mod(self.clk_buf)

        assert len(OPTS.write_buffers) % 2 == 1, "Number of write buffers should be odd"
        self.bitline_en = LogicBuffer(buffer_stages=OPTS.write_buffers, logic="pnand2", **self.get_logic_args())
        self.add_mod(self.bitline_en)

        self.create_wordline_en()
        self.create_sense_amp_en()

        assert len(OPTS.chb_buffers) % 2 == 1, "Number of matchline buffers should be odd"
        self.chb_buf = LogicBuffer(buffer_stages=OPTS.chb_buffers, logic="pnor2", **self.get_logic_args())
        self.add_mod(self.chb_buf)

    def create_wordline_en(self):
        assert len(OPTS.wordline_en_buffers) % 2 == 0, "Number of wordline buffers should be even"
        self.wordline_buf = LogicBuffer(buffer_stages=OPTS.wordline_en_buffers, logic="pnor2",
                                        **self.get_logic_args())
        self.add_mod(self.wordline_buf)

    def create_sense_amp_en(self):
        assert len(OPTS.sense_amp_buffers) % 2 == 0, "Number of sense_amp buffers should be even"
        self.sense_amp_buf = LogicBuffer(buffer_stages=OPTS.sense_amp_buffers, logic="pnor2", **self.get_logic_args())
        self.add_mod(self.sense_amp_buf)

    def add_modules(self):
        y_offset = self.rail_pos[-1] + self.m3_width + 0.5 * self.rail_height

        self.clk_search_inst_bar = self.add_inst("clk_search_bar", mod=self.nand, offset=vector(0, y_offset))
        self.connect_inst(["clk", "search", "clk_search_bar", "vdd", "gnd"])

        self.bitline_en_inst = self.add_inst("bitline_en", mod=self.bitline_en, offset=self.clk_search_inst_bar.lr())
        self.connect_inst(["bank_sel", "clk_search_bar", "bitline_en", "bitline_en_bar", "vdd", "gnd"])

        self.clk_sel_inst = self.add_inst("clk_sel", mod=self.nand, offset=self.bitline_en_inst.lr())
        self.connect_inst(["bank_sel", "clk", "clk_sel_bar", "vdd", "gnd"])

        self.clk_buf_inst = self.add_inst("clk_buf", mod=self.clk_buf, offset=self.clk_sel_inst.lr())
        self.connect_inst(["clk_sel_bar", "clk_buf", "clk_bar", "vdd", "gnd"])

        self.wordline_buf_inst = self.add_inst("wordline_en", mod=self.wordline_buf, offset=self.clk_buf_inst.lr())
        self.connect_inst(["search", "clk_sel_bar", "wordline_bar", "wordline_en", "vdd", "gnd"])

        self.search_bar_inst = self.add_inst("search_bar", mod=self.inv, offset=self.wordline_buf_inst.lr())
        self.connect_inst(["search", "search_bar", "vdd", "gnd"])

        self.chb_buf_inst = self.add_inst("chb", mod=self.chb_buf, offset=self.search_bar_inst.lr())
        self.connect_inst(["search_bar", "clk_sel_bar", "precharge_en_bar", "precharge_en", "vdd", "gnd"])

        self.sel_search_bar_inst = self.add_inst("sel_search_bar", mod=self.nand, offset=self.chb_buf_inst.lr())
        self.connect_inst(["bank_sel", "search", "sel_search_bar", "vdd", "gnd"])

        self.sense_amp_buf_inst = self.add_inst("sense_amp_buf", mod=self.sense_amp_buf,
                                                offset=self.sel_search_bar_inst.lr())
        self.connect_inst(["clk", "sel_search_bar", "sense_amp_bar", "sense_amp_en", "vdd", "gnd"])

    def add_input_pins(self):
        self.bank_sel_pin = self.add_layout_pin("bank_sel", "metal3", offset=vector(0, self.rail_pos[2]),
                                                width=self.sel_search_bar_inst.get_pin("A").cx())
        self.search_pin = self.add_layout_pin("search", "metal3", offset=vector(0, self.rail_pos[1]),
                                              width=self.sel_search_bar_inst.get_pin("A").lx())
        self.clk_pin = self.add_layout_pin("clk", "metal3", offset=vector(0, self.rail_pos[0]),
                                           width=self.sense_amp_buf_inst.get_pin("A").cx())

    def route_internal_signals(self):
        self.connect_a_pin(self.clk_search_inst_bar, self.clk_pin, via_dir="left")
        self.connect_b_pin(self.clk_search_inst_bar, self.search_pin, via_dir="left")

        self.connect_z_to_b(self.clk_search_inst_bar.get_pin("Z"), self.bitline_en_inst.get_pin("B"))
        self.connect_a_pin(self.bitline_en_inst, self.bank_sel_pin)

        self.connect_a_pin(self.clk_sel_inst, self.bank_sel_pin, via_dir="right")
        self.connect_b_pin(self.clk_sel_inst, self.clk_pin, via_dir="left")

        self.connect_z_to_a(self.clk_sel_inst, self.clk_buf_inst, a_name="in")

        z_pin = self.clk_sel_inst.get_pin("Z")
        clk_sel_bar_rail = self.add_rect("metal3", offset=vector(z_pin.lx(), self.rail_pos[3]),
                                         width=self.chb_buf_inst.get_pin("A").lx()-z_pin.lx())
        self.add_rect("metal2", offset=vector(z_pin.lx(), clk_sel_bar_rail.by()),
                      height=z_pin.by()-clk_sel_bar_rail.by())
        self.add_contact(m2m3.layer_stack, offset=vector(z_pin.lx(), clk_sel_bar_rail.by()))

        self.connect_a_pin(self.wordline_buf_inst, self.search_pin)
        self.connect_b_pin(self.wordline_buf_inst, clk_sel_bar_rail, via_dir="left")

        self.connect_inverter_in(self.search_bar_inst, self.search_pin)

        self.connect_z_to_a(self.search_bar_inst, self.chb_buf_inst, a_name="A")
        self.connect_b_pin(self.chb_buf_inst, clk_sel_bar_rail)

        self.connect_a_pin(self.sel_search_bar_inst, self.bank_sel_pin)
        self.connect_b_pin(self.sel_search_bar_inst, self.search_pin, via_dir="left")

        self.connect_z_to_b(self.sel_search_bar_inst.get_pin("Z"), self.sense_amp_buf_inst.get_pin("B"))
        self.connect_a_pin(self.sense_amp_buf_inst, self.clk_pin)

    def add_output_pins(self):
        pin_names = ["precharge_en_bar", "clk_buf", "sense_amp_en", "bitline_en", "wordline_en"]
        mod_names = self.get_output_pins()
        instances = [self.chb_buf_inst, self.clk_buf_inst, self.sense_amp_buf_inst, self.bitline_en_inst,
                     self.wordline_buf_inst]
        for i in range(len(pin_names)):
            out_pin = instances[i].get_pin(mod_names[i])
            self.add_layout_pin(pin_names[i], "metal2", offset=out_pin.ul(), height=self.height-out_pin.uy())

    @staticmethod
    def get_output_pins():
        return ["out_inv", "out_inv", "out", "out_inv", "out"]

    def add_power_pins(self):
        first_module = min(self.insts, key=lambda x: x.lx())
        first_module_gnd = first_module.get_pin("gnd")
        self.add_layout_pin("gnd", "metal1", offset=first_module_gnd.ll(), width=self.width-first_module_gnd.lx(),
                            height=first_module_gnd.height())
        first_module_vdd = first_module.get_pin("vdd")
        self.add_layout_pin("vdd", "metal1", offset=first_module_vdd.ll(), width=self.width-first_module_vdd.lx(),
                            height=first_module_vdd.height())

    def add_pins(self):
        pins_str = "bank_sel clk search clk_buf bitline_en sense_amp_en wordline_en precharge_en_bar vdd gnd"
        self.add_pin_list(pins_str.split(' '))
