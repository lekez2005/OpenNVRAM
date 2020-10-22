from base.vector import vector
from globals import OPTS
from modules.baseline_latched_control_buffers import LatchedControlBuffers as BaseLatchedControlBuffers
from modules.logic_buffer import LogicBuffer


class LatchedControlBuffers(BaseLatchedControlBuffers):
    """
    Difference with baseline is that baseline only enables precharge during reads.
    To prevent write errors, bitline need to be precharged even for un-selected columns
    So, for words_per_row > 1, precharge when bank is selected and clk is high independent of read or write
    """

    def get_num_rails(self):
        return 5

    def create_clk_pin(self):
        self.clk_pin = self.add_layout_pin("clk", "metal3", offset=vector(0, self.rail_pos[3]),
                                           width=self.clk_buf_inst.get_pin("A").cx())

    def add_modules(self):
        y_offset = self.height - self.nand.height

        self.clk_bar_inst = self.add_inst("clk_bar", mod=self.inv, offset=vector(0, y_offset))
        self.connect_inst(["clk", "clk_bar_int", "vdd", "gnd"])

        self.bank_sel_cbar_inst = self.add_inst("bank_sel_cbar", mod=self.nand_x2, offset=self.clk_bar_inst.lr())
        self.connect_inst(["bank_sel", "clk_bar_int", "bank_sel_cbar", "vdd", "gnd"])

        self.wordline_buf_inst = self.add_inst("wordline_buf", mod=self.wordline_buf,
                                               offset=self.bank_sel_cbar_inst.lr())
        self.connect_inst(["sense_trig", "bank_sel_cbar", "wordline_en_bar", "wordline_en", "vdd", "gnd"])

        self.precharge_buf_inst = self.add_inst("precharge_buf", mod=self.precharge_buf,
                                                offset=self.wordline_buf_inst.lr())
        self.connect_inst(["bank_sel", "clk", "precharge_en", "precharge_en_bar", "vdd", "gnd"])

        self.clk_buf_inst = self.add_inst("clk_buf", mod=self.clk_buf, offset=self.precharge_buf_inst.lr())
        self.connect_inst(["bank_sel", "clk", "clk_buf", "clk_bar", "vdd", "gnd"])

        self.write_buf_inst = self.add_inst("write_buf", mod=self.write_buf, offset=self.clk_buf_inst.lr())
        self.connect_inst(["read", "bank_sel_cbar", "write_en_bar", "write_en", "vdd", "gnd"])

        self.sel_clk_sense_inst = self.add_inst("sel_clk_sense", mod=self.nor, offset=self.write_buf_inst.lr())
        self.connect_inst(["sense_trig", "bank_sel_cbar", "sel_clk_sense", "vdd", "gnd"])

        self.sample_bar_int_inst = self.add_inst("sample_bar_int", mod=self.nand_x2,
                                                 offset=self.sel_clk_sense_inst.lr())
        self.connect_inst(["read", "sel_clk_sense", "sample_bar_int", "vdd", "gnd"])

        self.sample_bar_inst = self.add_inst("sample_bar", mod=self.sample_bar, offset=self.sample_bar_int_inst.lr())
        self.connect_inst(["sample_bar_int", "sample_en_buf", "sample_en_bar", "vdd", "gnd"])

        self.sense_amp_buf_inst = self.add_inst("sense_amp_buf", mod=self.sense_amp_buf,
                                                offset=self.sample_bar_inst.lr())
        self.connect_inst(["sample_bar_int", "sense_trig", "bank_sel", "sense_en", "sense_en_bar", "vdd", "gnd"])

        self.tri_en_buf_inst = self.add_inst("tri_en_buf", mod=self.tri_en_buf,
                                             offset=self.sense_amp_buf_inst.lr())
        self.connect_inst(["sample_bar_int", "sense_trig", "bank_sel", "tri_en", "tri_en_bar", "vdd", "gnd"])

    def create_precharge_buffers(self):
        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        logic_args = self.get_logic_args()
        self.precharge_buf = LogicBuffer(buffer_stages=OPTS.precharge_buffers, logic="pnand2", **logic_args)
        self.add_mod(self.precharge_buf)

    def route_internal_signals(self):
        self.connect_inverter_in(self.clk_bar_inst, self.clk_pin)

        self.connect_a_pin(self.bank_sel_cbar_inst, self.bank_sel_pin)
        # output of clk_bar to bank_sel_cbar_inst
        self.connect_z_to_b(self.clk_bar_inst.get_pin("Z"), self.bank_sel_cbar_inst.get_pin("B"))

        # bank_sel_cbar_inst output
        self.sel_cbar_rail = self.create_output_rail(self.bank_sel_cbar_inst.get_pin("Z"),
                                                     self.rail_pos[-1], self.sel_clk_sense_inst.get_pin("B"))
        # connect to wordline en
        self.connect_z_to_b(self.bank_sel_cbar_inst.get_pin("Z"), self.wordline_buf_inst.get_pin("B"))
        self.connect_a_pin(self.wordline_buf_inst, self.sense_trig_pin)

        self.route_precharge_buf()

        # clk_buf
        self.connect_a_pin(self.clk_buf_inst, self.bank_sel_pin, via_dir="left")
        self.connect_b_pin(self.clk_buf_inst, self.clk_pin, via_dir="left")

        # write buf
        self.connect_b_pin(self.write_buf_inst, self.sel_cbar_rail, via_dir="left")
        self.connect_a_pin(self.write_buf_inst, self.read_pin)

        # sel_clk_sense
        self.connect_b_pin(self.sel_clk_sense_inst, self.sel_cbar_rail, via_dir="left")
        self.connect_a_pin(self.sel_clk_sense_inst, self.sense_trig_pin)

        # sample_bar_int
        self.connect_z_to_b(self.sel_clk_sense_inst.get_pin("Z"), self.sample_bar_int_inst.get_pin("B"))
        self.connect_a_pin(self.sample_bar_int_inst, self.read_pin)

        # sample_bar
        self.connect_z_to_a(self.sample_bar_int_inst, self.sample_bar_inst, a_name="in")

        self.sample_bar_int_rail = self.create_output_rail(self.sample_bar_int_inst.get_pin("Z"),
                                                           self.read_pin,
                                                           self.tri_en_buf_inst.get_pin("A"), via_dir="left")

        self.route_sense_amp()
        self.route_tri_en()

    def route_precharge_buf(self):
        # route precharge_buf_inst
        self.connect_a_pin(self.precharge_buf_inst, self.bank_sel_pin, via_dir="right")
        self.connect_b_pin(self.precharge_buf_inst, self.clk_pin, via_dir="left")
