from globals import OPTS
from modules.baseline_latched_control_buffers import LatchedControlBuffers
from modules.buffer_stage import BufferStage
from modules.logic_buffer import LogicBuffer
from modules.mram.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers


class SotMramControlBuffers(SotfetMramControlBuffers):

    def create_sample_bar(self):
        pass

    def create_sense_amp_buf(self):
        self.sense_amp_buf = self.create_mod(LogicBuffer, buffer_stages="sense_amp_buffers",
                                             logic="pnand3")

    def create_tri_en_buf(self):
        self.tri_en_buf = self.create_mod(BufferStage, buffer_stages="tri_en_buffers")

    def get_rwl_connections(self):
        return [
            ("clk_bar_int", self.inv, ["clk", "clk_bar_int"]),
            ("rwl_buf", self.rwl_en, ["read", "bank_sel", "clk_bar_int", "rwl_en_bar", "rwl_en"])
        ]

    def add_sense_amp_connections(self, connections):
        # TODO sense_en rise has a very large impact on vref.
        #   It falls then rises back, the impact can extend of > 500 ps
        #   The tradeoff is to enable sense_en at clk_bar rather than sense_trig
        #   i.e. tradeoff more energy for less delay
        connections.extend([
            ("sense_en_bar", self.sense_amp_buf,
             ["read", "bank_sel", "clk_bar_int", "sense_en_bar", "sense_en"]),
            ("tri_en_int", self.nand, ["sense_trig", "bank_sel", "sense_en_int_bar"]),
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
