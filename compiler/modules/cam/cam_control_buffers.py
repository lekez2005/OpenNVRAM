from globals import OPTS
from modules.baseline_latched_control_buffers import LatchedControlBuffers
from modules.logic_buffer import LogicBuffer


class CamControlBuffers(LatchedControlBuffers):

    def has_precharge(self):
        return self.bank.words_per_row > 1

    def get_schematic_pins(self):
        in_pins = self.get_input_schematic_pins()
        in_pins[in_pins.index("read")] = "search"

        decoder_clk = ["decoder_clk"] * self.use_decoder_clk
        if not self.has_precharge():
            precharge_pins = ["ml_precharge_bar", "discharge"]
        else:
            precharge_pins = ["ml_precharge_bar", "discharge", "precharge_en_bar"]

        out_pins = decoder_clk + ["clk_buf", "clk_bar", "wordline_en", "search_sense_en",
                                  "write_en", "write_en_bar"] + precharge_pins
        self.remove_floating_pins([("en", "write_en"), ("en_bar", "write_en_bar")],
                                  out_pins, "write_driver_array")
        return in_pins, out_pins

    def create_wordline_en(self):
        assert len(OPTS.wordline_en_buffers) % 2 == 1, "Number of wordline buffers should be odd"
        self.wordline_buf = self.create_mod(LogicBuffer, logic="pnand3",
                                            buffer_stages="wordline_en_buffers")

    def create_write_buf(self):
        assert len(OPTS.write_buffers) % 2 == 1, "Number of write buffers should be odd"
        self.write_buf = self.create_mod(LogicBuffer, logic="pnand2",
                                         buffer_stages="write_buffers")

    def create_precharge_buffers(self):

        self.matchline_buf = self.create_mod(LogicBuffer,
                                             buffer_stages="ml_buffers",
                                             logic="pnor2")

        assert len(OPTS.precharge_buffers) % 2 == 1, \
            "Number of precharge_buffers should be odd"
        self.precharge_buf = self.create_mod(LogicBuffer,
                                             buffer_stages="precharge_buffers",
                                             logic="pnor2")

        self.discharge_buf = self.create_mod(LogicBuffer,
                                             buffer_stages="discharge_buffers",
                                             logic="pnor2")

    def create_sample_bar(self):
        pass

    def create_tri_en_buf(self):
        pass

    def create_schematic_connections(self):
        connections = [
            ("clk_buf", self.clk_buf,
             ["bank_sel", "clk", "clk_bar", "clk_buf"])
        ]
        self.add_precharge_buf_connections(connections)
        self.add_write_connections(connections)
        self.add_sense_connections(connections)
        self.add_decoder_clk_connections(connections)
        self.add_chip_sel_connections(connections)
        return connections

    def add_precharge_buf_connections(self, connections):
        precharge_in = "precharge_trig" if self.use_precharge_trigger else "clk"

        conns = [
            ("bar_sel_clk", self.nand_x2, ["bank_sel", precharge_in, "bar_sel_clk"]),
            ("search_bar", self.inv_x2, ["search", "search_bar"]),
            ("matchline_buf", self.matchline_buf,
             ["search_bar", "bar_sel_clk", "ml_precharge_buf", "ml_precharge_bar"]),
            ("discharge_buf", self.discharge_buf,
             ["search_bar", "bar_sel_clk", "discharge", "discharge_bar"])
        ]
        if self.bank.words_per_row > 1:
            conns.append(("precharge_buf", self.precharge_buf,
                          ["search", "bar_sel_clk", "precharge_buf", "precharge_en_bar"]))
        connections.extend(conns)

    def add_write_connections(self, connections):
        conns = [
            ("clk_bar_int", self.inv, ["clk", "clk_bar_int"]),
            ("write_buf", self.write_buf,
             ["bank_sel", "clk_bar_int", "write_en_bar", "write_en"]),
            ("wordline_buf", self.wordline_buf,
             ["bank_sel", "clk_bar_int", "search_bar", "wordline_en_bar", "wordline_en"])
        ]
        connections.extend(conns)

    def add_sense_connections(self, connections):
        connections.append(("sense_amp_buf", self.sense_amp_buf,
                            ["search", "bank_sel", "sense_trig", "search_en_bar",
                             "search_sense_en"]))
