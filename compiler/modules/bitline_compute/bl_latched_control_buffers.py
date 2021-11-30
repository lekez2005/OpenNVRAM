from globals import OPTS
from modules.bitline_compute.bl_control_buffers_base import BlControlBuffersBase
from modules.buffer_stage import BufferStage
from modules.logic_buffer import LogicBuffer
from pgates.pnand3 import pnand3


class LatchedControlBuffers(BlControlBuffersBase):
    """
    Differs from baseline control buffers in sense_en. sense_en is only disabled during precharge and sample

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
        sense_en:   NOR(precharge, sample)
                    = AND(precharge_bar, sample_bar)
    """

    def create_modules(self):
        self.create_common_modules()
        self.nand3 = self.create_mod(pnand3, size=1.2)
        self.create_decoder_clk()
        self.create_clk_buf()
        self.create_wordline_en()
        self.create_write_buf()
        self.create_precharge_buffers()
        self.creates_sense_precharge_buf()
        self.create_sample_bar()
        self.create_sense_amp_buf()

    def create_sense_amp_buf(self):
        assert len(OPTS.sense_amp_buffers) % 2 == 1, "Number of sense_en buffers should be odd"
        self.sense_amp_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.sense_amp_buffers,
                                             logic="pnand2")

    def create_precharge_buffers(self):
        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        self.precharge_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.precharge_buffers,
                                             logic="pnand2")

    def creates_sense_precharge_buf(self):
        assert len(OPTS.sense_precharge_buffers) % 2 == 0, \
            "Number of precharge buffers should be even"
        self.sense_precharge_buf = self.create_mod(BufferStage,
                                                   buffer_stages=OPTS.sense_precharge_buffers)

    def create_schematic_connections(self):
        connections = [
            ("precharge_buf", self.precharge_buf,
             ["bank_sel", "clk", "precharge_en_bar", "precharge_en"]),
            ("precharge_bar_int", self.nand3,
             ["read", "bank_sel", "clk", "precharge_bar_int"]),
            ("sense_precharge_buf", self.sense_precharge_buf,
             ["precharge_bar_int", "sense_precharge_en", "sense_precharge_bar"]),
            ("clk_buf", self.clk_buf, ["bank_sel", "clk", "clk_bar", "clk_buf"]),
            ("clk_bar", self.inv, ["clk", "clk_bar_int"]),
            ("bank_sel_cbar", self.nand_x2, ["bank_sel", "clk_bar_int", "bank_sel_cbar"]),
            ("wordline_buf", self.wordline_buf,
             ["sense_trig", "bank_sel_cbar", "wordline_en", "wordline_en_bar"]),
            ("write_buf", self.write_buf, ["read", "bank_sel_cbar", "write_en", "write_en_bar"]),
            ("sel_clk_sense", self.nor, ["sense_trig", "bank_sel_cbar", "sel_clk_sense"]),
            ("sample_bar_int", self.nand_x2, ["read", "sel_clk_sense", "sample_bar_int"]),
            ("sample_bar", self.sample_bar, ["sample_bar_int", "sample_en_buf", "sample_en_bar"]),
            ("sense_amp_buf", self.sense_amp_buf,
             ["precharge_bar_int", "sample_bar_int", "sense_en_bar", "sense_en"])
        ]
        self.add_decoder_clk_connections(connections)
        return connections

    def get_schematic_pins(self):
        return [
            ["bank_sel", "read", "clk", "sense_trig"],
            self.get_bank_clocks() +
            ["clk_bar", "wordline_en", "precharge_en_bar", "write_en",
             "write_en_bar", "sense_en", "sense_precharge_bar", "sample_en_bar"]
        ]
