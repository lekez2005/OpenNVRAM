from modules.baseline_bank import LEFT_FILL, RIGHT_FILL, JOIN_BOT_ALIGN, JOIN_TOP_ALIGN
from modules.shared_decoder.sot.sot_mram_control_buffers import SotMramControlBuffers
from modules.shared_decoder.sotfet.mram_bank import MramBank


class SotMramBank(MramBank):

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

    def get_sense_amp_array_connections(self):
        connections = super().get_sense_amp_array_connections()
        connections[connections.index("ref_bl")] = "ref_bl_out"
        connections[connections.index("ref_br")] = "ref_br_out"
        return connections

    def add_vref_pin(self):
        x_offset = self.vref_x_offset
        self.route_external_control_pin("vclamp", inst=self.sense_amp_array_inst,
                                        x_offset=x_offset)

    def route_layout(self):
        super().route_layout()
        self.join_ref_bitlines()

    def join_ref_bitlines(self):
        combinations = [
            (self.precharge_array_inst, ["ref_bl", "ref_br"],
             self.bitcell_array_inst, ["ref_bl", "ref_br"], JOIN_TOP_ALIGN),
            (self.col_mux_array_inst, ["ref_bl", "ref_br"],
             self.precharge_array_inst, ["ref_bl", "ref_br"], JOIN_TOP_ALIGN),
            (self.sense_amp_array_inst, ["ref_bl", "ref_br"],
             self.col_mux_array_inst, ["ref_bl_out", "ref_br_out"], JOIN_BOT_ALIGN),
            (self.write_driver_array_inst, ["ref_bl", "ref_br"],
             self.sense_amp_array_inst, ["ref_bl", "ref_br"], JOIN_TOP_ALIGN)
        ]

        alignments = [LEFT_FILL, RIGHT_FILL]
        for j, (bottom_inst, bottom_names, top_inst, top_names, rect_align) in \
                enumerate(combinations):
            for i in range(len(bottom_names)):
                template = "{}" if j > 1 else "{}[{}]"
                num_bits = 1 if j > 1 else 2
                top_pins = [top_inst.get_pin(template.format(top_names[i], x))
                            for x in range(num_bits)]
                bottom_pins = [bottom_inst.get_pin(template.format(bottom_names[i], x))
                               for x in range(num_bits)]

                self.join_rects(top_pins, top_pins[0].layer, bottom_pins, bottom_pins[0].layer,
                                alignments[i], rect_align=rect_align)
