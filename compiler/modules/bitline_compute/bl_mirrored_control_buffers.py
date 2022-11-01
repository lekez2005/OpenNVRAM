from globals import OPTS
from modules.bitline_compute.bl_control_buffers_base import BlControlBuffersBase
from modules.buffer_stage import BufferStage
from modules.logic_buffer import LogicBuffer
from pgates.pnand2 import pnand2


class BlMirroredControlBuffers(BlControlBuffersBase):
    """
    Generate and buffer control signals using bank_sel, clk and read
    Assumes write if read_bar, bitline computation vs read difference is handled at decoder level
    Inputs:
        bank_sel, read, clk, sense_trig
    Define internal signal
        bank_sel_cbar = clk_bar.bank_sel
    Outputs
        wordline_en: bank_sel_cbar
        clk_buf:     clk_bank_sel_bar
        precharge_en_bar: and3(read, read, bank_sel)
        write_en:     bank_sel_cbar.read_bar
        sense_en: bank_sel.sense_trig (same as tri_en)
        tri_en_bar: sense_en_bar
    """

    def create_modules(self):
        self.create_common_modules()
        self.nand_x2 = self.create_mod(pnand2, size=2)
        self.create_decoder_clk()
        self.create_clk_buf()
        self.create_wordline_en()
        self.create_write_buf()
        self.create_precharge_buffers()
        self.create_sample_bar()
        self.create_sense_amp_buf()

        if self.has_tri_state:
            self.create_tri_en_buf()

    def create_schematic_connections(self):
        connections = [
            ("precharge_buf", self.precharge_buf,
             ["read", "bank_sel", "clk", "precharge_en_bar", "precharge_en"]),
            ("clk_buf", self.clk_buf,
             ["bank_sel", "clk", "clk_bar", "clk_buf"]),
            ("clk_bar", self.inv, ["clk", "clk_bar_int"]),
            ("bank_sel_cbar", self.nand_x2,
             ["bank_sel", "clk_bar_int", "bank_sel_cbar"]),
            ("wordline_buf", self.wordline_buf,
             ["bank_sel_cbar", "wordline_en", "wordline_en_bar"]),
            ("write_buf", self.write_buf,
             ["bank_sel_cbar", "read", "write_en", "write_en_bar"]),
            ("read_bar", self.inv, ["read", "read_bar"]),
            ("sense_amp_buf", self.sense_amp_buf,
             ["bank_sel_cbar", "read_bar", "sense_en", "sense_en_bar"]),
        ]
        if self.has_tri_state:
            self.add_tri_state_connections(connections)
        self.add_decoder_clk_connections(connections)
        return connections

    def create_sense_amp_buf(self):
        self.sense_amp_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.sense_amp_buffers,
                                             logic="pnor2")

    def create_tri_en_buf(self):
        self.tri_en_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.tri_en_buffers,
                                          logic="pnor2")

    def create_precharge_buffers(self):
        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        self.precharge_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.precharge_buffers,
                                             logic="pnand3")

    def create_wordline_en(self):
        assert len(OPTS.wordline_en_buffers) % 2 == 1, "Number of wordline buffers should be odd"
        self.wordline_buf = self.create_mod(BufferStage,
                                            buffer_stages="wordline_en_buffers")

    def add_tri_state_connections(self, connections):
        connections.append(("tri_en_buf", self.tri_en_buf,
                            ["bank_sel_cbar", "read_bar", "tri_en", "tri_en_bar"]))

    def get_schematic_pins(self):
        self.has_tri_state = getattr(OPTS, "has_tri_state", True)
        if self.has_tri_state:
            tri_pins = ["tri_en", "tri_en_bar"]
        else:
            tri_pins = []
        return (["bank_sel", "read", "clk"],
                self.get_bank_clocks() +
                ["clk_bar", "wordline_en", "precharge_en_bar",
                 "write_en", "write_en_bar", "sense_en", "sense_en_bar"] + tri_pins)
