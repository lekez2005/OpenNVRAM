from globals import OPTS
from modules.buffer_stage import BufferStage
from modules.control_buffers import ControlBuffers
from modules.logic_buffer import LogicBuffer
from pgates.pinv import pinv
from pgates.pnand2 import pnand2
from pgates.pnor2 import pnor2


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

    def create_modules(self):
        self.nand = self.create_mod(pnand2)
        self.nor = self.create_mod(pnor2)
        self.inv = self.create_mod(pinv)

        self.clk_buf = self.create_mod(BufferStage, buffer_stages=OPTS.clk_buffers)

        assert len(OPTS.write_buffers) % 2 == 1, "Number of write buffers should be odd"
        self.bitline_en = self.create_mod(LogicBuffer, buffer_stages=OPTS.write_buffers,
                                          logic="pnand2")

        self.create_wordline_en()
        self.create_sense_amp_en()

        assert len(OPTS.chb_buffers) % 2 == 1, "Number of matchline buffers should be odd"
        self.chb_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.chb_buffers,
                                       logic="pnor2")

    def create_wordline_en(self):
        assert len(OPTS.wordline_en_buffers) % 2 == 0, "Number of wordline buffers should be even"
        self.wordline_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.wordline_en_buffers,
                                            logic="pnor2")

    def create_sense_amp_en(self):
        assert len(OPTS.sense_amp_buffers) % 2 == 0, "Number of sense_amp buffers should be even"
        self.sense_amp_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.sense_amp_buffers,
                                             logic="pnor2")

    def create_schematic_connections(self):
        connections = [
            ("clk_search_bar", self.nand, ["clk", "search", "clk_search_bar"]),
            ("bitline_en", self.bitline_en,
             ["bank_sel", "clk_search_bar", "bitline_en_bar", "bitline_en"]),
            ("clk_sel", self.nand, ["bank_sel", "clk", "clk_sel_bar"]),
            ("clk_buf", self.clk_buf, ["clk_sel_bar", "clk_bar", "clk_buf"]),
            ("wordline_en", self.wordline_buf,
             ["search", "clk_sel_bar", "wordline_en", "wordline_bar"]),
            ("search_bar", self.inv, ["search", "search_bar"]),
            ("chb", self.chb_buf,
             ["search_bar", "clk_sel_bar", "precharge_en", "precharge_en_bar"]),
            ("sel_search_bar", self.nand, ["bank_sel", "search", "sel_search_bar"]),
            ("sense_amp_buf", self.sense_amp_buf,
             ["clk", "sel_search_bar", "sense_amp_en", "sense_amp_bar"]),
        ]
        return connections

    def get_schematic_pins(self):
        return (
            ["bank_sel", "clk", "search"],
            ["clk_buf", "bitline_en", "sense_amp_en", "wordline_en", "precharge_en_bar"]
        )
