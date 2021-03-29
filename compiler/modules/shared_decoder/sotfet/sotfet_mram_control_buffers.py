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
        self.precharge_buf = self.create_mod(LogicBuffer, buffer_stages="precharge_buffers",
                                             logic="pnand3")
        self.br_reset_buf = self.create_mod(LogicBuffer, buffer_stages="br_reset_buffers",
                                            logic="pnand2")

    def create_wordline_en(self):
        assert len(OPTS.wordline_en_buffers) % 2 == 1, "Number of rwl buffers should be odd"
        self.rwl_en = self.create_mod(LogicBuffer, buffer_stages="wordline_en_buffers",
                                      logic="pnand3")

        assert len(OPTS.wwl_en_buffers) % 2 == 1, "Number of wwl buffers should be odd"
        self.wwl_en = self.create_mod(BufferStage, buffer_stages="wwl_en_buffers")

    def create_write_buf(self):
        assert len(OPTS.write_buffers) % 2 == 1, "Number of write buffers should be odd"
        self.write_buf = self.create_mod(BufferStage, buffer_stages="write_buffers")

    def create_schematic_connections(self):
        sense_conns = ["sample_en_bar", "sense_trig", "bank_sel", "sense_en_bar", "sense_en"]
        connections = [
            ("nor_trig_clk", self.nor, ["sense_trig", "clk", "nor_trig_clk"]),
            ("rwl_buf", self.rwl_en, ["nor_trig_clk", "read", "bank_sel", "rwl_en", "rwl_en_bar"]),
            ("clk_buf", self.clk_buf, ["bank_sel", "clk", "clk_bar", "clk_buf"]),
            ("nor_read_clk", self.nor, ["read", "clk", "nor_read_clk"]),
            ("wwl_en_int_bar", self.nand, ["nor_read_clk", "bank_sel", "wwl_en_int_bar"]),
            ("wwl_en", self.wwl_en, ["wwl_en_int_bar", "wwl_en", "wwl_en_bar"]),
            ("write_buf", self.write_buf, ["wwl_en_int_bar", "write_en_bar", "write_en"]),
            ("sense_trig_bar", self.inv, ["sense_trig", "sense_trig_bar"]),

            ("sample_bar_int", self.nand3, ["bank_sel", "read", "sense_trig_bar", "sample_bar_int"]),

            ("sample_bar", self.sample_bar,
             ["sample_bar_int", "sample_en_buf", "sample_en_bar"]),
            ("sense_amp_buf", self.sense_amp_buf,
             ["sample_bar_int", "sense_trig", "bank_sel", "sense_en_bar", "sense_en"]),
            ("tri_en_buf", self.tri_en_buf,
             ["sample_bar_int", "sense_trig", "bank_sel", "tri_en_bar", "tri_en"])
        ]
        self.add_precharge_buf_connections(connections)
        self.add_decoder_clk_connections(connections)
        self.add_chip_sel_connections(connections)
        return connections

    def add_precharge_buf_connections(self, connections):
        precharge_in = "precharge_trig" if self.use_precharge_trigger else "clk"
        nets = ["read"] + [precharge_in, "bank_sel", "precharge_en_bar", "precharge_en"]
        connections.insert(0, ("precharge_buf", self.precharge_buf, nets))
        connections.insert(1, ("br_reset", self.br_reset_buf, ["read", "bank_sel", "br_reset_bar", "br_reset"]))

    def get_schematic_pins(self):
        in_pins, out_pins = super().get_schematic_pins()
        out_pins.remove("wordline_en")
        out_pins.extend(["rwl_en", "wwl_en", "br_reset"])
        return in_pins, out_pins
