from base.vector import vector
from globals import OPTS
from modules.logic_buffer import LogicBuffer
from modules.sotfet.sf_control_buffers import SfControlBuffers
from pgates.pinv import pinv


class SwControlBuffers(SfControlBuffers):
    """
    Generate and buffer control signals using bank_sel, clk and search pins
    define clk_search_bar = NAND(clk, search)
    clk_buf = bank_sel.clk
    bitline_en = bank_sel.clk_bar
        = AND(bank_sel, clk_bar)
    wordline_en = bank_sel.clk_bar.search_bar
        = AND(bank_sel, NOR(clk, search))
    precharge_en_bar = bank_sel.clk.search
        = NOR(search_bar, NAND(clk, search)
        = NOR(search_bar, clk_search_bar)
    sense_amp_en = bank_sel.clk_bar.search
        = NOR(clk, NAND(bank_sel, search))
    """
    inv2 = None

    def create_modules(self):
        super().create_modules()
        self.inv2 = pinv(size=2, **self.get_common_args())

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

        self.search_bar_inst = self.add_inst("search_bar", mod=self.inv, offset=self.sense_amp_buf_inst.lr())
        self.connect_inst(["search", "search_bar", "vdd", "gnd"])

        self.wordline_buf_inst = self.add_inst("wordline_en", mod=self.wordline_buf, offset=self.search_bar_inst.lr())
        self.connect_inst(["bank_sel", "search_bar", "clk_bar_int", "wordline_en", "wordline_bar", "vdd", "gnd"])

        self.chb_buf_inst = self.add_inst("chb", mod=self.chb_buf, offset=self.wordline_buf_inst.lr())
        self.connect_inst(["search_bar", "clk_sel_bar", "precharge_en_bar", "precharge_en", "vdd", "gnd"])

    def add_input_pins(self):
        self.bank_sel_pin = self.add_layout_pin("bank_sel", "metal3", offset=vector(0, self.rail_pos[2]),
                                                width=self.wordline_buf_inst.get_pin("A").cx())
        self.search_pin = self.add_layout_pin("search", "metal3", offset=vector(0, self.rail_pos[1]),
                                              width=self.search_bar_inst.get_pin("A").lx())
        self.clk_pin = self.add_layout_pin("clk", "metal3", offset=vector(0, self.rail_pos[0]),
                                           width=self.clk_bar_inst.get_pin("A").cx())

    def route_internal_signals(self):
        self.connect_a_pin(self.clk_sel_inst, self.bank_sel_pin, via_dir="right")
        self.connect_b_pin(self.clk_sel_inst, self.clk_pin, via_dir="left")

        self.connect_z_to_a(self.clk_sel_inst, self.clk_buf_inst, a_name="in")

        clk_sel_bar_rail = self.create_output_rail(self.clk_sel_inst.get_pin("Z"), self.rail_pos[3],
                                                   self.chb_buf_inst.get_pin("A"))

        self.connect_inverter_in(self.clk_bar_inst, self.clk_pin)

        clk_bar_rail = self.create_output_rail(self.clk_bar_inst.get_pin("Z"), self.clk_pin,
                                               self.wordline_buf_inst.get_pin("C"))

        self.connect_z_to_b(self.clk_bar_inst.get_pin("Z"), self.bitline_en_inst.get_pin("B"))
        self.connect_a_pin(self.bitline_en_inst, self.bank_sel_pin)

        self.connect_a_pin(self.sense_amp_buf_inst, self.bank_sel_pin)
        self.connect_b_pin(self.sense_amp_buf_inst, self.search_pin, via_dir="left")
        self.connect_c_pin(self.sense_amp_buf_inst, clk_bar_rail)

        self.connect_inverter_in(self.search_bar_inst, self.search_pin)

        search_bar_rail = self.create_output_rail(self.search_bar_inst.get_pin("Z"), self.search_pin,
                                                  self.chb_buf_inst.get_pin("A"))

        self.connect_z_to_b(self.search_bar_inst.get_pin("Z"), self.wordline_buf_inst.get_pin("B"))
        self.connect_a_pin(self.wordline_buf_inst, self.bank_sel_pin)
        self.connect_c_pin(self.wordline_buf_inst, clk_bar_rail)

        self.connect_a_pin(self.chb_buf_inst, search_bar_rail)
        self.connect_b_pin(self.chb_buf_inst, clk_sel_bar_rail, via_dir="left")

    @staticmethod
    def get_output_pins():
        return ["out_inv", "out_inv", "out_inv", "out_inv", "out_inv"]
