from globals import OPTS
from modules.baseline_latched_control_buffers import LatchedControlBuffers
from modules.logic_buffer import LogicBuffer
from modules.mram.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers


class SotfetMramControlBuffers1t1s(SotfetMramControlBuffers):

    def create_precharge_buffers(self):
        assert len(OPTS.precharge_buffers) % 2 == 0, \
            "Number of precharge buffers should be even"
        self.precharge_buf = self.create_mod(LogicBuffer,
                                             buffer_stages="precharge_buffers",
                                             logic="pnand2")
        self.br_precharge_buf = self.create_mod(LogicBuffer,
                                                buffer_stages="precharge_buffers",
                                                logic="pnand3")

    def create_sample_bar(self):
        assert len(OPTS.sampleb_buffers) % 2 == 0, \
            "Number of sampleb buffers should be even"
        self.sample_bar = self.create_mod(LogicBuffer,
                                          buffer_stages="sampleb_buffers",
                                          logic="pnand3")

    def add_precharge_buf_connections(self, connections):
        precharge_in = "precharge_trig" if self.use_precharge_trigger else "clk"
        nets = [precharge_in, "bank_sel", "precharge_en_bar", "precharge_en"]
        connections.insert(0, ("precharge_buf", self.precharge_buf, nets))

        connections.insert(1, ("read_bar", self.inv, ["read", "read_bar"]))
        nets = [precharge_in, "bank_sel", "read_bar", "br_precharge_en_bar", "br_precharge_en"]
        connections.insert(2, ("br_precharge", self.br_precharge_buf, nets))

    def add_sense_amp_connections(self, connections):
        if getattr(OPTS, "mirror_sense_amp", False):
            sense_nets = ["sense_trig", "bank_sel", "read", "sense_en_bar", "sense_en"]
        else:
            sense_nets = ["sense_trig", "bank_sel", "sample_en_bar",
                          "sense_en_bar", "sense_en"]
        connections.extend([
            ("sense_trig_bar", self.inv, ["sense_trig", "sense_trig_bar"]),
            ("sample_bar", self.sample_bar,
             ["bank_sel", "read", "sense_trig_bar", "sample_en_bar", "br_reset"]),
            ("sense_amp_buf", self.sense_amp_buf, sense_nets),
            ("tri_en_buf", self.tri_en_buf,
             ["sense_trig", "bank_sel", "sample_en_bar", "tri_en_bar", "tri_en"])
        ])

    def get_schematic_pins(self):
        in_pins, out_pins = LatchedControlBuffers.get_schematic_pins(self)
        in_pins.append("write_trig")
        out_pins.remove("wordline_en")
        out_pins.remove("sample_en_bar")
        out_pins.extend(["rwl_en", "wwl_en", "br_precharge_en_bar", "br_reset"])
        return in_pins, out_pins
