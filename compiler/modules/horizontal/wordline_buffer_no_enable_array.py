from modules.horizontal.wordline_buffer import WordlineBuffer
from modules.horizontal.wordline_buffer_array import wordline_buffer_array
from modules.horizontal.wordline_pgate_tap import wordline_pgate_tap


class wordline_buffer_no_enable_array(wordline_buffer_array):

    def connect_inst(self, args, check=True):
        if "en" in args:
            args.remove("en")
        super().connect_inst(args, check)

    def create_layout(self):
        self.create_modules()
        self.add_modules()

    def add_pins(self):
        super().add_pins()
        self.pins.remove("en")

    def add_in_pin(self, buffer_inst, row):
        # route in pin
        self.copy_layout_pin(buffer_inst, "in", "in[{}]".format(row))

    def route_en_pin(self, *_, **__):
        pass

    def add_en_pin(self):
        return None, None

    def get_buffer_x_offset(self, _):
        return 0

    def get_reference_mod(self):
        return self.buffer.buffer_invs[0]

    def create_buffer(self):
        self.buffer = self.logic_buffer = \
            WordlineBuffer(buffer_stages=self.buffer_stages, route_outputs=False)
        self.add_mod(self.buffer)

    def add_tap_insts(self):
        self.tap_insts = []
        for y_offset in self.tap_offsets:
            tap_insts = wordline_pgate_tap.add_buffer_taps(self, 0, y_offset,
                                                           self.buffer.module_insts,
                                                           self.pwell_tap,
                                                           self.nwell_tap)
            self.tap_insts.extend(tap_insts)
