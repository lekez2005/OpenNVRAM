from globals import OPTS
from modules.baseline_latched_control_buffers import LatchedControlBuffers
from modules.buffer_stage import BufferStage
from modules.logic_buffer import LogicBuffer
from modules.mram.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers


class SotMramControlBuffers(SotfetMramControlBuffers):

    def create_sample_bar(self):
        pass

    def create_sense_amp_buf(self):
        self.sense_en_bar = self.create_mod(LogicBuffer, buffer_stages="sense_en_bar_buffers",
                                            logic="pnand3")
        assert len(OPTS.sense_amp_buffers) % 2 == 1, "Number of sense_en buffers should be odd"
        self.sense_amp_buf = self.create_mod(BufferStage, buffer_stages="sense_amp_buffers")

    def create_tri_en_buf(self):
        self.tri_en_buf = self.create_mod(BufferStage, buffer_stages="tri_en_buffers")

    def add_sense_amp_connections(self, connections):
        connections.extend([
            ("clk_bar_int", self.inv, ["clk", "clk_bar_int"]),
            ("sense_en_bar", self.sense_en_bar,
             ["read", "bank_sel", "clk_bar_int", "sense_en_bar", "sense_en_bar_buf"]),
            ("sense_en_int", self.nand, ["sense_trig", "bank_sel", "sense_en_int_bar"]),
            ("sense_amp_buf", self.sense_amp_buf,
             ["sense_en_int_bar", "sense_en", "sense_en_buf_bar"]),
            ("tri_en_buf", self.tri_en_buf,
             ["sense_en_int_bar", "tri_en", "tri_en_bar"])
        ])

    def get_schematic_pins(self):
        self.extract_precharge_inputs()
        in_pins, out_pins = LatchedControlBuffers.get_schematic_pins(self)
        in_pins.append("write_trig")
        out_pins.remove("wordline_en")
        out_pins.remove("sample_en_bar")
        if not self.has_precharge_bl:
            out_pins.remove("precharge_en_bar")
        out_pins.extend(["rwl_en", "wwl_en", "bl_reset", "br_reset"])
        return in_pins, out_pins
