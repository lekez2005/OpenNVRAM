from globals import OPTS
from modules.baseline_latched_control_buffers import LatchedControlBuffers as BaseLatchedControlBuffers
from modules.buffer_stage import BufferStage
from modules.logic_buffer import LogicBuffer


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

    def create_precharge_buffers(self):
        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        self.precharge_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.precharge_buffers,
                                             logic="pnand2")
        self.br_precharge_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.precharge_buffers,
                                                logic="pnand3")

    def create_wordline_en(self):
        assert len(OPTS.wordline_en_buffers) % 2 == 1, "Number of rwl buffers should be odd"
        self.rwl_en = self.create_mod(LogicBuffer, buffer_stages=OPTS.wordline_en_buffers,
                                      logic="pnand3")

        assert len(OPTS.wordline_en_buffers) % 2 == 1, "Number of wwl buffers should be odd"
        self.wwl_en = self.create_mod(BufferStage, buffer_stages=OPTS.wordline_en_buffers)

    def create_write_buf(self):
        assert len(OPTS.write_buffers) % 2 == 1, "Number of write buffers should be odd"
        self.write_buf = self.create_mod(BufferStage, buffer_stages=OPTS.write_buffers)

    def create_sample_bar(self):
        assert len(OPTS.sampleb_buffers) % 2 == 0, "Number of sampleb buffers should be even"
        self.sample_bar = self.create_mod(LogicBuffer, buffer_stages=OPTS.sampleb_buffers,
                                          logic="pnand3")

    def create_sense_amp_buf(self):
        if not OPTS.mirror_sense_amp:
            assert len(OPTS.sense_amp_buffers) % 2 == 1, \
                "Number of sense_en buffers should be odd"
        self.sense_amp_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.sense_amp_buffers,
                                             logic="pnand3")

    def create_schematic_connections(self):
        if OPTS.mirror_sense_amp:
            sense_conns = ["read", "sense_trig", "bank_sel", "sense_en", "sense_en_bar"]
        else:
            sense_conns = ["sample_en_bar", "sense_trig", "bank_sel",
                           "sense_en", "sense_en_bar"]
        connections = [
            ("nor_trig_clk", self.nor, ["sense_trig", "clk", "nor_trig_clk"]),
            ("rwl_buf", self.rwl_en, ["nor_trig_clk", "read", "bank_sel", "rwl_en", "rwl_en_bar"]),
            ("precharge_buf", self.precharge_buf, ["bank_sel", "clk", "precharge_en",
                                                   "precharge_en_bar"]),
            ("read_bar", self.inv, ["read", "read_bar"]),
            ("br_precharge_buf", self.br_precharge_buf,
             ["read_bar", "bank_sel", "clk", "br_precharge_en", "br_precharge_en_bar"]),
            ("nor_read_clk", self.nor, ["read", "clk", "nor_read_clk"]),
            ("wwl_en_int_bar", self.nand, ["nor_read_clk", "bank_sel", "wwl_en_int_bar"]),
            ("wwl_en", self.wwl_en, ["wwl_en_int_bar", "wwl_en", "wwl_en_bar"]),
            ("clk_buf", self.clk_buf, ["bank_sel", "clk", "clk_buf", "clk_bar"]),
            ("write_buf", self.write_buf, ["wwl_en_int_bar", "write_en", "write_en_bar"]),
            ("sense_trig_bar", self.inv, ["sense_trig", "sense_trig_bar"]),
            ("sample_bar", self.sample_bar, ["sense_trig_bar", "bank_sel", "read",
                                             "br_reset", "sample_en_bar"]),
            ("sense_amp_buf", self.sense_amp_buf, sense_conns),
            ("tri_en_buf", self.tri_en_buf, ["sample_en_bar", "sense_trig", "bank_sel",
                                             "tri_en", "tri_en_bar"])
        ]
        return connections

    def get_schematic_pins(self):
        additional_pin = "sense_en_bar" if OPTS.mirror_sense_amp else "sample_en_bar"
        return (
            ["bank_sel", "read", "clk", "sense_trig"],
            ["clk_buf", "clk_bar", "rwl_en", "wwl_en", "precharge_en_bar",
             "br_precharge_en_bar", "write_en", "write_en_bar",
             "sense_en", "tri_en", "tri_en_bar", "br_reset", additional_pin]
        )
