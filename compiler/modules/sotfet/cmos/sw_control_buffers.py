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

    def create_modules(self):
        super().create_modules()
        self.inv2 = self.create_mod(pinv, size=2)

    def create_wordline_en(self):
        assert len(OPTS.wordline_en_buffers) % 2 == 1, "Number of wordline buffers should be odd"
        self.wordline_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.wordline_en_buffers,
                                            logic="pnand3")

    def create_sense_amp_en(self):
        assert len(OPTS.sense_amp_buffers) % 2 == 1, "Number of sense_amp buffers should be odd"
        self.sense_amp_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.sense_amp_buffers,
                                             logic="pnand3")
        self.add_mod(self.sense_amp_buf)

    def create_schematic_connections(self):
        connections = [
            ("clk_sel", self.nand, ["bank_sel", "clk", "clk_sel_bar"]),
            ("clk_buf", self.clk_buf, ["clk_sel_bar", "clk_buf", "clk_bar"]),
            ("clk_bar_int", self.inv2, ["clk", "clk_bar_int"]),
            ("bitline_en", self.bitline_en,
             ["bank_sel", "clk_bar_int", "bitline_en_bar", "bitline_en"]),
            ("sense_amp_buf", self.sense_amp_buf,
             ["bank_sel", "search", "clk_bar_int", "sense_amp_bar", "sense_amp_en"]),
            ("search_bar", self.inv, ["search", "search_bar"]),
            ("wordline_en", self.wordline_buf,
             ["bank_sel", "search_bar", "clk_bar_int", "wordline_bar", "wordline_en"]),
            ("chb", self.chb_buf,
             ["search_bar", "clk_sel_bar", "precharge_en", "precharge_en_bar"])
        ]
        return connections
