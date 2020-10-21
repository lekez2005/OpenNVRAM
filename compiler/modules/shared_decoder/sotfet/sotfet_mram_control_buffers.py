from base.vector import vector
from globals import OPTS
from modules.baseline_latched_control_buffers import LatchedControlBuffers as BaseLatchedControlBuffers
from modules.buffer_stage import BufferStage
from modules.logic_buffer import LogicBuffer
from pgates.pinv import pinv
from pgates.pnand2 import pnand2
from pgates.pnand3 import pnand3
from pgates.pnor2 import pnor2


class SotfetMramControlBuffers(BaseLatchedControlBuffers):
    """
    Inputs:
        bank_sel, read, clk, sense_trig
    Define internal signal
        bank_sel_cbar = NAND(clk_bar, bank_sel)
    Stages:

    rwl_en:             and4(sense_trig_bar, read, clk_bar, bank_sel)
                        = AND3(NOR(sense_trig, clk), read, bank_sel)

    precharge_en_bar:   and3(read, clk, bank_sel)

    wwl_en_int_bar:     nand3(read_bar, clk_bar, bank_sel)
                        = nand(NOR(read, clk), bank_sel)

    wwl_en:             wwl_en_int buffer

    clk_buf:            bank_sel.clk

    write_en:           wwl_en_int buffer

    sampleb:            nand3(bank_sel, sense_trig_bar, read)
                        = nand3( INV(sense_trig), bank_sel, read)

    sense_en:           and3(bank_sel, sense_trig, sampleb) (same as tri_en)
                        ensures sense_en is after sampleb

    tri_en:             sense_en
    """

    def get_num_rails(self):
        return 5

    def add_input_pins(self):
        self.clk_pin = self.add_layout_pin("clk", "metal3", offset=vector(0, self.rail_pos[3]),
                                           width=self.clk_buf_inst.get_pin("A").cx())

        if OPTS.mirror_sense_amp:
            dest_pin = self.sense_amp_buf_inst.get_pin("B")
        else:
            dest_pin = self.sample_bar_inst.get_pin("B")
        self.read_pin = self.add_layout_pin("read", "metal3", offset=vector(0, self.rail_pos[0]),
                                            width=dest_pin.cx())

        self.sense_trig_pin = self.add_layout_pin("sense_trig", "metal3", offset=vector(0, self.rail_pos[1]),
                                                  width=self.tri_en_buf_inst.get_pin("A").lx())

        self.bank_sel_pin = self.add_layout_pin("bank_sel", "metal3", offset=vector(0, self.rail_pos[2]),
                                                width=self.tri_en_buf_inst.get_pin("B").cx())

    def create_modules(self):
        common_args = self.get_common_args()
        buffer_args = self.get_buffer_args()
        logic_args = self.get_logic_args()

        self.nand = pnand2(**common_args)
        self.add_mod(self.nand)

        self.nor = pnor2(**common_args)
        self.add_mod(self.nor)

        self.nand3 = pnand3(**common_args)
        self.add_mod(self.nand3)

        self.inv = pinv(**common_args)
        self.add_mod(self.inv)

        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        self.precharge_buf = LogicBuffer(buffer_stages=OPTS.precharge_buffers, logic="pnand2", **logic_args)
        self.add_mod(self.precharge_buf)

        self.br_precharge_buf = LogicBuffer(buffer_stages=OPTS.precharge_buffers, logic="pnand3", **logic_args)
        self.add_mod(self.br_precharge_buf)

        assert len(OPTS.wordline_en_buffers) % 2 == 1, "Number of rwl buffers should be odd"
        self.rwl_en = LogicBuffer(buffer_stages=OPTS.wordline_en_buffers,
                                  logic="pnand3", **logic_args)
        self.add_mod(self.rwl_en)

        assert len(OPTS.wordline_en_buffers) % 2 == 1, "Number of wwl buffers should be odd"
        self.wwl_en = BufferStage(buffer_stages=OPTS.wordline_en_buffers, **buffer_args)
        self.add_mod(self.wwl_en)

        self.clk_buf = LogicBuffer(buffer_stages=OPTS.clk_buffers, logic="pnand2", **logic_args)
        self.add_mod(self.clk_buf)

        assert len(OPTS.write_buffers) % 2 == 1, "Number of write buffers should be odd"
        self.write_buf = BufferStage(buffer_stages=OPTS.write_buffers, **buffer_args)
        self.add_mod(self.write_buf)

        assert len(OPTS.sampleb_buffers) % 2 == 0, "Number of sampleb buffers should be even"
        self.sample_bar = LogicBuffer(buffer_stages=OPTS.sampleb_buffers,
                                      logic="pnand3", **logic_args)
        self.add_mod(self.sample_bar)

        if not OPTS.mirror_sense_amp:
            assert len(OPTS.sense_amp_buffers) % 2 == 1, \
                "Number of sense_en buffers should be odd"
        self.sense_amp_buf = LogicBuffer(buffer_stages=OPTS.sense_amp_buffers, logic="pnand3",
                                         **logic_args)
        self.add_mod(self.sense_amp_buf)

        self.tri_en_buf = LogicBuffer(buffer_stages=OPTS.tri_en_buffers, logic="pnand3", **logic_args)
        self.add_mod(self.tri_en_buf)

    def add_modules(self):
        y_offset = self.height - self.nand.height

        self.nor_trig_clk_inst = self.add_inst("nor_trig_clk", mod=self.nor,
                                               offset=vector(0, y_offset))
        self.connect_inst(["sense_trig", "clk", "nor_trig_clk", "vdd", "gnd"])

        self.rwl_buf_inst = self.add_inst("rwl_buf", mod=self.rwl_en,
                                          offset=self.nor_trig_clk_inst.lr())
        self.connect_inst(["nor_trig_clk", "read", "bank_sel", "rwl_en", "rwl_en_bar",
                           "vdd", "gnd"])

        self.precharge_buf_inst = self.add_inst("precharge_buf", mod=self.precharge_buf,
                                                offset=self.rwl_buf_inst.lr())
        self.connect_inst(["bank_sel", "clk", "precharge_en", "precharge_en_bar", "vdd", "gnd"])

        self.read_bar_inst = self.add_inst("read_bar", mod=self.inv, offset=self.precharge_buf_inst.lr())
        self.connect_inst(["read", "read_bar", "vdd", "gnd"])

        self.br_precharge_buf_inst = self.add_inst("br_precharge_buf", mod=self.br_precharge_buf,
                                                   offset=self.read_bar_inst.lr())
        self.connect_inst(["read_bar", "bank_sel", "clk", "br_precharge_en",
                           "br_precharge_en_bar", "vdd", "gnd"])

        self.nor_read_clk_inst = self.add_inst("nor_read_clk", mod=self.nor,
                                               offset=self.br_precharge_buf_inst.lr())
        self.connect_inst(["read", "clk", "nor_read_clk", "vdd", "gnd"])

        self.wwl_en_int_bar_inst = self.add_inst("wwl_en_int_bar", mod=self.nand,
                                                 offset=self.nor_read_clk_inst.lr())
        self.connect_inst(["nor_read_clk", "bank_sel", "wwl_en_int_bar", "vdd", "gnd"])

        self.wwl_en_inst = self.add_inst("wwl_en", mod=self.wwl_en,
                                         offset=self.wwl_en_int_bar_inst.lr())
        self.connect_inst(["wwl_en_int_bar", "wwl_en", "wwl_en_bar", "vdd", "gnd"])

        self.clk_buf_inst = self.add_inst("clk_buf", mod=self.clk_buf, offset=self.wwl_en_inst.lr())
        self.connect_inst(["bank_sel", "clk", "clk_buf", "clk_bar", "vdd", "gnd"])

        self.write_buf_inst = self.add_inst("write_buf", mod=self.write_buf,
                                            offset=self.clk_buf_inst.lr())
        self.connect_inst(["wwl_en_int_bar", "write_en", "write_en_bar", "vdd", "gnd"])

        self.sense_trig_bar_inst = self.add_inst("sense_trig_bar", mod=self.inv,
                                                 offset=self.write_buf_inst.lr())
        self.connect_inst(["sense_trig", "sense_trig_bar", "vdd", "gnd"])

        self.sample_bar_inst = self.add_inst("sample_bar", mod=self.sample_bar,
                                             offset=self.sense_trig_bar_inst.lr())
        self.connect_inst(["sense_trig_bar", "bank_sel", "read",
                           "br_reset", "sample_en_bar", "vdd", "gnd"])

        self.sense_amp_buf_inst = self.add_inst("sense_amp_buf", mod=self.sense_amp_buf,
                                                offset=self.sample_bar_inst.lr())
        if OPTS.mirror_sense_amp:
            self.connect_inst(["read", "sense_trig", "bank_sel",
                               "sense_en", "sense_en_bar", "vdd", "gnd"])
        else:
            self.connect_inst(["sample_en_bar", "sense_trig", "bank_sel",
                               "sense_en", "sense_en_bar", "vdd", "gnd"])

        self.tri_en_buf_inst = self.add_inst("tri_en_buf", mod=self.tri_en_buf,
                                             offset=self.sense_amp_buf_inst.lr())
        self.connect_inst(["sample_en_bar", "sense_trig", "bank_sel",
                           "tri_en", "tri_en_bar", "vdd", "gnd"])

    def route_internal_signals(self):
        self.connect_a_pin(self.nor_trig_clk_inst, self.sense_trig_pin, via_dir="left")
        self.connect_b_pin(self.nor_trig_clk_inst, self.clk_pin, via_dir="left")

        self.connect_z_to_a(self.nor_trig_clk_inst, self.rwl_buf_inst)
        self.connect_b_pin(self.rwl_buf_inst, self.read_pin)
        self.connect_c_pin(self.rwl_buf_inst, self.bank_sel_pin)

        self.connect_a_pin(self.precharge_buf_inst, self.bank_sel_pin, via_dir="left")
        self.connect_b_pin(self.precharge_buf_inst, self.clk_pin, via_dir="left")

        self.connect_inverter_in(self.read_bar_inst, self.read_pin)
        self.connect_z_to_a(self.read_bar_inst, self.br_precharge_buf_inst)
        self.connect_b_pin(self.br_precharge_buf_inst, self.bank_sel_pin)
        self.connect_c_pin(self.br_precharge_buf_inst, self.clk_pin)

        self.connect_a_pin(self.nor_read_clk_inst, self.read_pin, via_dir="left")
        self.connect_b_pin(self.nor_read_clk_inst, self.clk_pin, via_dir="left")

        self.connect_z_to_a(self.nor_read_clk_inst, self.wwl_en_int_bar_inst)
        self.connect_b_pin(self.wwl_en_int_bar_inst, self.bank_sel_pin)

        self.connect_z_to_a(self.wwl_en_int_bar_inst, self.wwl_en_inst, a_name="in")
        self.wwl_en_int_bar_rail = self.create_output_rail(self.wwl_en_int_bar_inst.get_pin("Z"),
                                                           self.rail_pos[-1],
                                                           self.write_buf_inst.get_pin("in"))

        self.connect_a_pin(self.clk_buf_inst, self.bank_sel_pin, via_dir="left")
        self.connect_b_pin(self.clk_buf_inst, self.clk_pin, via_dir="left")

        self.connect_a_pin(self.write_buf_inst, self.wwl_en_int_bar_rail, pin_name="in")

        self.connect_inverter_in(self.sense_trig_bar_inst, self.sense_trig_pin)

        self.connect_z_to_a(self.sense_trig_bar_inst, self.sample_bar_inst)
        self.connect_b_pin(self.sample_bar_inst, self.bank_sel_pin, via_dir="left")
        self.connect_c_pin(self.sample_bar_inst, self.read_pin, via_dir="left")

        self.sample_bar_rail = self.create_output_rail(self.sample_bar_inst.get_pin("out"),
                                                       self.rail_pos[-1],
                                                       self.tri_en_buf_inst.get_pin("A"), via_dir="left")

        if OPTS.mirror_sense_amp:
            self.connect_a_pin(self.sense_amp_buf_inst, self.read_pin)
        else:
            self.connect_z_to_a(self.sample_bar_inst, self.sense_amp_buf_inst, z_name="out")
        self.connect_b_pin(self.sense_amp_buf_inst, self.sense_trig_pin, via_dir="left")
        self.connect_c_pin(self.sense_amp_buf_inst, self.bank_sel_pin, via_dir="left")

        self.connect_a_pin(self.tri_en_buf_inst, self.sample_bar_rail, via_dir="right")
        self.connect_b_pin(self.tri_en_buf_inst, self.sense_trig_pin, via_dir="left")
        self.connect_c_pin(self.tri_en_buf_inst, self.bank_sel_pin, via_dir="left")

    def add_pins(self):
        self.add_pin_list(["bank_sel", "read", "clk", "sense_trig", "clk_buf", "clk_bar",
                           "rwl_en", "wwl_en", "precharge_en_bar", "br_precharge_en_bar", "write_en", "write_en_bar",
                           "sense_en", "tri_en", "tri_en_bar", "br_reset",
                           "vdd", "gnd"])
        if OPTS.mirror_sense_amp:
            self.add_pin("sense_en_bar")
        else:
            self.add_pin("sample_en_bar")

    def add_output_pins(self):
        if OPTS.mirror_sense_amp:
            custom_pins = [("sense_en_bar", "out", self.sense_amp_buf_inst)]
        else:
            custom_pins = [("sample_en_bar", "out", self.sample_bar_inst)]
        pin_names = ["br_precharge_en_bar", "precharge_en_bar", "clk_buf", "clk_bar", "rwl_en",
                     "wwl_en", "write_en", "write_en_bar", "sense_en", "tri_en",
                     "tri_en_bar", "br_reset"]
        mod_names = ["out", "out", "out_inv", "out", "out_inv", "out_inv", "out_inv", "out",
                     "out_inv", "out_inv", "out", "out_inv"]
        instances = [self.br_precharge_buf_inst, self.precharge_buf_inst, self.clk_buf_inst, self.clk_buf_inst,
                     self.rwl_buf_inst, self.wwl_en_inst, self.write_buf_inst,
                     self.write_buf_inst, self.sense_amp_buf_inst, self.tri_en_buf_inst,
                     self.tri_en_buf_inst, self.sample_bar_inst]

        for pin_name, mod_name, inst in custom_pins:
            pin_names.append(pin_name)
            mod_names.append(mod_name)
            instances.append(inst)

        for i in range(len(pin_names)):
            out_pin = instances[i].get_pin(mod_names[i])
            self.add_layout_pin(pin_names[i], "metal2", offset=out_pin.ul(), height=self.height - out_pin.uy())
