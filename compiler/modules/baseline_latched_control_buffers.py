from modules.control_buffers import ControlBuffers


class LatchedControlBuffers(ControlBuffers):
    """
    Generate and buffer control signals using bank_sel, clk and read
    Assumes write if read_bar, bitline computation vs read difference is handled at decoder level
    Inputs:
        bank_sel, read, clk, sense_trig
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

    def create_modules(self):
        self.create_common_modules()
        self.create_clk_buf()
        self.create_wordline_en()
        self.create_write_buf()
        self.create_precharge_buffers()
        self.create_sense_amp_buf()
        self.create_sample_bar()
        self.create_tri_en_buf()

    def create_schematic_connections(self):
        connections = [
            ("precharge_buf", self.precharge_buf,
             ["bank_sel", "clk", "precharge_en", "precharge_en_bar"]),
            ("clk_buf", self.clk_buf,
             ["bank_sel", "clk", "clk_buf", "clk_bar"]),
            ("clk_bar", self.inv, ["clk", "clk_bar_int"]),
            ("bank_sel_cbar", self.nand_x2,
             ["bank_sel", "clk_bar_int", "bank_sel_cbar"]),
            ("wordline_buf", self.wordline_buf,
             ["sense_trig", "bank_sel_cbar", "wordline_en_bar", "wordline_en"]),
            ("write_buf", self.write_buf,
             ["read", "bank_sel_cbar", "write_en_bar", "write_en"]),
            ("sel_clk_sense", self.nor,
             ["sense_trig", "bank_sel_cbar", "sel_clk_sense"]),
            ("sample_bar_int", self.nand_x2,
             ["read", "sel_clk_sense", "sample_bar_int"]),
            ("sample_bar", self.sample_bar,
             ["sample_bar_int", "sample_en_buf", "sample_en_bar"]),
            ("sense_amp_buf", self.sense_amp_buf,
             ["sample_bar_int", "sense_trig", "bank_sel", "sense_en", "sense_en_bar"]),
            ("tri_en_buf", self.tri_en_buf,
             ["sample_bar_int", "sense_trig", "bank_sel", "tri_en", "tri_en_bar"])
        ]
        return connections

    def get_schematic_pins(self):
        return (["bank_sel", "read", "clk", "sense_trig"],
                ["clk_buf", "clk_bar", "wordline_en", "precharge_en_bar",
                 "write_en", "write_en_bar", "sense_en", "tri_en",
                 "tri_en_bar", "sample_en_bar"])
