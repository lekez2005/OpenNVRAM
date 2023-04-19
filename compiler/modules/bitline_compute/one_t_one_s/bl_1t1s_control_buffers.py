import debug
from globals import OPTS
from modules.buffer_stage import BufferStage
from modules.logic_buffer import LogicBuffer
from modules.mram.sotfet.sotfet_mram_control_buffers import SotfetMramControlBuffers


class Bl1t1sControlBuffers(SotfetMramControlBuffers):
    def extract_precharge_inputs(self):
        self.one_wpr = self.bank.words_per_row == 1
        self.has_precharge_bl = True
        self.has_bl_reset = False
        self.has_br_reset = False

    def create_write_buf(self):
        assert len(OPTS.write_buffers) % 2 == 0, "Number of write buffers should be even"
        self.write_buf = self.create_mod(BufferStage, buffer_stages="write_buffers")

    def create_precharge_buffers(self):
        self.creates_sense_precharge_buf()
        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        self.precharge_buf = self.create_mod(LogicBuffer,
                                             buffer_stages="precharge_buffers",
                                             logic="pnand3")

    def create_sense_amp_buf(self):
        assert len(OPTS.sense_amp_buffers) % 2 == 0, "Number of sense_en buffers should be even"
        self.sense_amp_buf = self.create_mod(LogicBuffer, buffer_stages="sense_amp_buffers",
                                             logic="pnor2")

    def creates_sense_precharge_buf(self):
        assert len(OPTS.sense_precharge_buffers) % 2 == 0, \
            "Number of precharge buffers should be even"
        self.sense_precharge_buf = self.create_mod(LogicBuffer, logic="pnand3",
                                                   buffer_stages="sense_precharge_buffers")

    def add_precharge_buf_connections(self, connections):
        # precharge_en_bar
        precharge_in = "precharge_trig" if self.use_precharge_trigger else "clk"
        nets = ["read", precharge_in, "bank_sel", "precharge_en_bar", "precharge_en"]
        connections.insert(0, ("precharge_buf", self.precharge_buf, nets))

    def add_sense_amp_connections(self, connections):
        connections.append(("sample_bar", self.sample_bar,
                            ["rwl_en", "sample_en_bar", "sample_en_buf"]))

        connections.extend([
            # sense_en
            ("trig_sel_bar", self.nand, ["bank_sel", "sense_trig", "trig_sel_bar"]),
            ("sense_amp_buf", self.sense_amp_buf,
             ["trig_sel_bar", "sample_en_buf", "sense_en", "sense_en_bar"]),
            # sense_precharge_bar
            ("sample_trig_bar", self.nor, ["sense_trig", "sample_en_buf", "sample_trig_bar"]),
            ("sense_precharge_buf", self.sense_precharge_buf,
             ["read", "bank_sel", "sample_trig_bar", "sense_precharge_bar", "sense_precharge_en"])
        ])

    def get_schematic_pins(self):
        in_pins, out_pins = super().get_schematic_pins()
        for pin_name in ["tri_en", "tri_en_bar", "sense_en_bar", "write_en"]:
            if pin_name in out_pins:
                out_pins.remove(pin_name)
        out_pins.append("sense_precharge_bar")
        debug.info(2, f"Control input pins: {', '.join(in_pins)}")
        debug.info(2, f"Control output pins: {', '.join(out_pins)}")
        return in_pins, out_pins
