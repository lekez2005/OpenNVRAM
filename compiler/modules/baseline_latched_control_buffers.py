from base.vector import vector
from globals import OPTS
from modules.buffer_stage import BufferStage
from modules.control_buffers import ControlBuffers
from modules.logic_buffer import LogicBuffer
from pgates.pinv import pinv
from pgates.pnand2 import pnand2
from pgates.pnor2 import pnor2


class LatchedControlBuffers(ControlBuffers):
    """
    Generate and buffer control signals using bank_sel, clk and read
    Assumes write if read_bar, bitline computation vs read difference is handled at decoder level
    Inputs:
        bank_sel, read, clk
    Define internal signal
        bank_sel_cbar = NAND(clk_bar, bank_sel)
    Outputs

        clk_buf:            bank_sel.clk
        precharge_en_bar:   and3(read, clk, bank_sel)
        write_en:           and3(read_bar, clk_bar, bank_sel) = nor(read, bank_sel_cbar)
        wordline_en: and3((sense_trig_bar + read_bar), bank_sel, clk_bar)
                    = nor(bank_sel_cbar, nor(sense_trig_bar, read_bar))
                    = nor(bank_sel_cbar, and(sense_trig, read)) sense_trig = 0 during writes
                    =       nor(bank_sel_cbar, sense_trig)
        sampleb:    NAND4(bank_sel, sense_trig_bar, clk_bar, read)
                    = NAND2(AND(bank_sel.clk_bar, sense_trig_bar), read)
                    = NAND2(nor(bank_sel_cbar, sense_trig), read)
                    =       nand2( nor(bank_sel_cbar, sense_trig), read)
        sense_en:           and3(bank_sel, sense_trig, sampleb) (same as tri_en) # ensures sense_en is after sampleb
        tri_en_bar: sense_en_bar
    """
    name = "control_buffers"

    nand = nor = inv = clk_buf = write_buf = sense_amp_buf = wordline_buf = precharge_buf = sample_bar = None
    clk_bar_inst = bank_sel_cbar_inst = read_bar_inst = None
    clk_buf_inst = write_buf_inst = sense_amp_buf_inst = wordline_buf_inst = precharge_buf_inst = None
    tri_en_buf_inst = sample_bar_inst = sample_bar_int_inst = sel_clk_sense_inst = None

    bank_sel_pin = clk_pin = read_pin = sel_cbar_rail = sense_trig_pin = None

    rail_pos = [0.0]*4

    def create_modules(self):
        common_args = self.get_common_args()
        buffer_args = self.get_buffer_args()
        logic_args = self.get_logic_args()

        self.nand = pnand2(**common_args)
        self.add_mod(self.nand)

        self.nand_x2 = pnand2(size=1.8, **common_args)
        self.add_mod(self.nand_x2)

        self.nor = pnor2(**common_args)
        self.add_mod(self.nor)

        self.inv = pinv(**common_args)
        self.add_mod(self.inv)

        self.clk_buf = LogicBuffer(buffer_stages=OPTS.clk_buffers, logic="pnand2", **logic_args)
        self.add_mod(self.clk_buf)

        assert len(OPTS.wordline_en_buffers) % 2 == 0, "Number of wordline buffers should be even"
        self.wordline_buf = LogicBuffer(buffer_stages=OPTS.wordline_en_buffers, logic="pnor2", **logic_args)
        self.add_mod(self.wordline_buf)

        self.write_buf = LogicBuffer(buffer_stages=OPTS.write_buffers, logic="pnor2", **logic_args)
        self.add_mod(self.write_buf)

        self.create_precharge_buffers()

        assert len(OPTS.sampleb_buffers) % 2 == 0, "Number of sampleb buffers should be even"
        self.sample_bar = BufferStage(buffer_stages=OPTS.sampleb_buffers, **buffer_args)
        self.add_mod(self.sample_bar)

        assert len(OPTS.sense_amp_buffers) % 2 == 1, "Number of sense_en buffers should be odd"
        self.sense_amp_buf = LogicBuffer(buffer_stages=OPTS.sense_amp_buffers, logic="pnand3", **logic_args)
        self.add_mod(self.sense_amp_buf)

        self.tri_en_buf = LogicBuffer(buffer_stages=OPTS.tri_en_buffers, logic="pnand3", **logic_args)
        self.add_mod(self.tri_en_buf)

    def create_precharge_buffers(self):
        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        logic_args = self.get_logic_args()
        self.precharge_buf = LogicBuffer(buffer_stages=OPTS.precharge_buffers, logic="pnand3", **logic_args)
        self.add_mod(self.precharge_buf)

    def add_modules(self):
        y_offset = self.height - self.nand.height

        self.precharge_buf_inst = self.add_inst("precharge_buf", mod=self.precharge_buf,
                                                offset=vector(0, y_offset))
        self.connect_inst(["read", "bank_sel", "clk", "precharge_en", "precharge_en_bar", "vdd", "gnd"])

        self.clk_buf_inst = self.add_inst("clk_buf", mod=self.clk_buf, offset=self.precharge_buf_inst.lr())
        self.connect_inst(["bank_sel", "clk", "clk_buf", "clk_bar", "vdd", "gnd"])

        self.clk_bar_inst = self.add_inst("clk_bar", mod=self.inv, offset=self.clk_buf_inst.lr())
        self.connect_inst(["clk", "clk_bar_int", "vdd", "gnd"])

        self.bank_sel_cbar_inst = self.add_inst("bank_sel_cbar", mod=self.nand_x2, offset=self.clk_bar_inst.lr())
        self.connect_inst(["bank_sel", "clk_bar_int", "bank_sel_cbar", "vdd", "gnd"])

        self.wordline_buf_inst = self.add_inst("wordline_buf", mod=self.wordline_buf,
                                               offset=self.bank_sel_cbar_inst.lr())
        self.connect_inst(["sense_trig", "bank_sel_cbar", "wordline_en_bar", "wordline_en", "vdd", "gnd"])

        self.write_buf_inst = self.add_inst("write_buf", mod=self.write_buf, offset=self.wordline_buf_inst.lr())
        self.connect_inst(["read", "bank_sel_cbar", "write_en_bar", "write_en", "vdd", "gnd"])

        self.sel_clk_sense_inst = self.add_inst("sel_clk_sense", mod=self.nor, offset=self.write_buf_inst.lr())
        self.connect_inst(["sense_trig", "bank_sel_cbar", "sel_clk_sense", "vdd", "gnd"])

        self.sample_bar_int_inst = self.add_inst("sample_bar_int", mod=self.nand_x2, offset=self.sel_clk_sense_inst.lr())
        self.connect_inst(["read", "sel_clk_sense", "sample_bar_int", "vdd", "gnd"])

        self.sample_bar_inst = self.add_inst("sample_bar", mod=self.sample_bar, offset=self.sample_bar_int_inst.lr())
        self.connect_inst(["sample_bar_int", "sample_en_buf", "sample_en_bar", "vdd", "gnd"])

        self.sense_amp_buf_inst = self.add_inst("sense_amp_buf", mod=self.sense_amp_buf,
                                                offset=self.sample_bar_inst.lr())
        self.connect_inst(["sense_trig", "bank_sel", "read", "sense_en", "sense_en_bar", "vdd", "gnd"])

        self.tri_en_buf_inst = self.add_inst("tri_en_buf", mod=self.tri_en_buf,
                                             offset=self.sense_amp_buf_inst.lr())
        self.connect_inst(["sense_trig", "bank_sel", "read", "tri_en", "tri_en_bar", "vdd", "gnd"])

    def add_input_pins(self):

        self.clk_pin = self.add_layout_pin("clk", "metal3", offset=vector(0, self.rail_pos[3]),
                                           width=self.clk_bar_inst.get_pin("A").cx())

        self.read_pin = self.add_layout_pin("read", "metal3", offset=vector(0, self.rail_pos[0]),
                                            width=self.tri_en_buf_inst.get_pin("C").cx())

        self.sense_trig_pin = self.add_layout_pin("sense_trig", "metal3", offset=vector(0, self.rail_pos[1]),
                                                  width=self.tri_en_buf_inst.get_pin("A").cx())

        self.bank_sel_pin = self.add_layout_pin("bank_sel", "metal3", offset=vector(0, self.rail_pos[2]),
                                                width=self.tri_en_buf_inst.get_pin("A").lx())

    def route_internal_signals(self):

        self.route_precharge_buf()

        # clk_buf
        self.connect_a_pin(self.clk_buf_inst, self.bank_sel_pin, via_dir="left")
        self.connect_b_pin(self.clk_buf_inst, self.clk_pin, via_dir="left")

        self.connect_inverter_in(self.clk_bar_inst, self.clk_pin)

        self.connect_a_pin(self.bank_sel_cbar_inst, self.bank_sel_pin)
        # output of clk_bar to bank_sel_cbar_inst
        self.connect_z_to_b(self.clk_bar_inst.get_pin("Z"), self.bank_sel_cbar_inst.get_pin("B"))

        # bank_sel_cbar_inst output
        self.sel_cbar_rail = self.create_output_rail(self.bank_sel_cbar_inst.get_pin("Z"),
                                                     self.clk_pin, self.sel_clk_sense_inst.get_pin("B"))

        # connect to wordline en
        self.connect_z_to_b(self.bank_sel_cbar_inst.get_pin("Z"), self.wordline_buf_inst.get_pin("B"))
        self.connect_a_pin(self.wordline_buf_inst, self.sense_trig_pin)

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

        # sense amp
        self.connect_a_pin(self.sense_amp_buf_inst, self.sense_trig_pin)
        self.connect_b_pin(self.sense_amp_buf_inst, self.bank_sel_pin, via_dir="left")
        self.connect_c_pin(self.sense_amp_buf_inst, self.read_pin, via_dir="right")

        self.connect_a_pin(self.tri_en_buf_inst, self.sense_trig_pin)
        self.connect_b_pin(self.tri_en_buf_inst, self.bank_sel_pin, via_dir="left")
        self.connect_c_pin(self.tri_en_buf_inst, self.read_pin, via_dir="right")

    def route_precharge_buf(self):
        # route precharge_buf_inst
        self.connect_a_pin(self.precharge_buf_inst, self.read_pin, via_dir="right")
        self.connect_b_pin(self.precharge_buf_inst, self.bank_sel_pin, via_dir="left")
        self.connect_c_pin(self.precharge_buf_inst, self.clk_pin, via_dir="right")

    def add_output_pins(self):
        pin_names = ["precharge_en_bar", "clk_buf", "clk_bar", "wordline_en", "write_en", "write_en_bar",
                     "sense_en", "tri_en", "tri_en_bar", "sample_en_bar"]
        mod_names = ["out", "out_inv", "out", "out", "out", "out_inv", "out_inv", "out_inv", "out", "out"]
        instances = [self.precharge_buf_inst, self.clk_buf_inst, self.clk_buf_inst, self.wordline_buf_inst,
                     self.write_buf_inst, self.write_buf_inst, self.sense_amp_buf_inst, self.tri_en_buf_inst,
                     self.tri_en_buf_inst, self.sample_bar_inst]
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
        self.add_pin_list(["bank_sel", "read", "clk", "sense_trig", "clk_buf", "clk_bar", "wordline_en",
                           "precharge_en_bar", "write_en", "write_en_bar",
                           "sense_en", "tri_en", "tri_en_bar", "sample_en_bar", "vdd", "gnd"])
