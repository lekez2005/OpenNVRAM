from modules.baseline_bank import LEFT_FILL, RIGHT_FILL, JOIN_BOT_ALIGN, JOIN_TOP_ALIGN
from modules.shared_decoder.sot.sot_mram_control_buffers import SotMramControlBuffers
from modules.shared_decoder.sotfet.sotfet_mram_bank_thin import SotfetMramBankThin


class SotMramBank(SotfetMramBankThin):

    def add_pins(self):
        super().add_pins()
        self.add_pin("vclamp")

    def create_control_buffers(self):
        self.control_buffers = SotMramControlBuffers(self)
        self.add_mod(self.control_buffers)

    def get_col_mux_connections(self):
        connections = self.connections_from_mod(self.column_mux_array, [])
        return connections

    def get_bitcell_array_connections(self):
        return self.connections_from_mod(self.bitcell_array, [])

    def add_vref_pin(self):
        x_offset = self.vref_x_offset
        self.route_external_control_pin("vclamp", inst=self.sense_amp_array_inst,
                                        x_offset=x_offset)

    def route_layout(self):
        super().route_layout()
        self.join_ref_bitlines()

    def join_ref_bitlines(self):
        combinations = [
            (self.sense_amp_array_inst, ["ref_bl", "ref_br"],
             self.col_mux_array_inst, ["ref_bl_out", "ref_br_out"]),
            (self.col_mux_array_inst, ["ref_bl", "ref_br"],
             self.precharge_array_inst, ["ref_bl", "ref_br"]),
            (self.precharge_array_inst, ["ref_bl", "ref_br"],
             self.bitcell_array_inst, ["ref_bl", "ref_br"])
        ]

        alignments = [LEFT_FILL, RIGHT_FILL]
        for j, (bottom_inst, bottom_names, top_inst, top_names) in enumerate(combinations):
            for i in range(len(bottom_names)):
                top_pins = [top_inst.get_pin("{}[{}]".format(top_names[i], x))
                            for x in range(2)]
                bottom_pins = [bottom_inst.get_pin("{}[{}]".format(bottom_names[i], x))
                               for x in range(2)]
                if j == 0:
                    rect_align = JOIN_BOT_ALIGN
                else:
                    rect_align = JOIN_TOP_ALIGN

                self.join_rects(top_pins, top_pins[0].layer, bottom_pins, bottom_pins[0].layer,
                                alignments[i], rect_align=rect_align)
