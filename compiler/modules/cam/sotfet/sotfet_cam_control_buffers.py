from globals import OPTS
from modules.cam.cam_control_buffers import CamControlBuffers
from modules.logic_buffer import LogicBuffer


class SotfetCamControlBuffers(CamControlBuffers):

    def get_schematic_pins(self):
        in_pins, out_pins = super().get_schematic_pins()
        in_pins.append("write_trig")
        return in_pins, out_pins

    def has_precharge(self):
        return False

    def create_write_buf(self):
        assert len(OPTS.write_buffers) % 2 == 1, "Number of write buffers should be odd"
        self.write_buf = self.create_mod(LogicBuffer, buffer_stages="write_buffers",
                                         logic="pnor2")

    def create_wordline_en(self):
        assert len(OPTS.wordline_en_buffers) % 2 == 1, "Number of wordline buffers should be odd"
        self.wordline_buf = self.create_mod(LogicBuffer, logic="pnor2",
                                            buffer_stages="wordline_en_buffers")

    def create_precharge_buffers(self):
        assert len(OPTS.ml_buffers) % 2 == 0, "Number of ml_buffers should be even"
        self.matchline_buf = self.create_mod(LogicBuffer,
                                             buffer_stages="ml_buffers",
                                             logic="pnand3")
        assert len(OPTS.discharge_buffers) % 2 == 1, "Number of discharge_buffers should be odd"
        self.discharge_buf = self.create_mod(LogicBuffer,
                                             buffer_stages="discharge_buffers",
                                             logic="pnand2")

    def add_precharge_buf_connections(self, connections):
        precharge_in = "precharge_trig" if self.use_precharge_trigger else "clk"
        conns = [
            ("matchline_buf", self.matchline_buf,
             [precharge_in, "bank_sel", "search",
              "ml_precharge_bar", "ml_precharge_buf"]),
            ("discharge_buf", self.discharge_buf,
             [precharge_in, "bank_sel", "discharge_bar", "discharge"])
        ]
        connections.extend(conns)

    def add_write_connections(self, connections):
        conns = [
            ("clk_bar_int", self.inv, ["clk", "clk_bar_int"]),
            ("bar_sel_clk_bar", self.nand, ["bank_sel", "clk_bar_int", "bar_sel_clk_bar"]),
            # write_en
            ("bar_write_trig_search", self.nor,
             ["write_trig", "search", "bar_write_trig_search"]),
            ("write_buf", self.write_buf,
             ["bar_write_trig_search", "bar_sel_clk_bar", "write_en", "write_en_bar"]),
            # wordline_en
            ("write_trig_bar", self.inv, ["write_trig", "write_trig_bar"]),
            ("wordline_buf", self.wordline_buf,
             ["write_trig_bar", "bar_sel_clk_bar", "wordline_en", "wordline_en_bar"])
        ]
        connections.extend(conns)
