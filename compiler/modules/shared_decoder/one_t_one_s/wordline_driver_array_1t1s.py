from base.vector import vector
from modules.shared_decoder.one_t_one_s.wordline_driver_mixin import wordline_driver_mixin
from modules.wordline_driver_array import wordline_driver_array
from pgates.pgate_tap import pgate_tap


class wordline_driver_array_1t1s(wordline_driver_mixin, wordline_driver_array):

    def add_modules(self):
        super().add_modules()
        rw_pin = self.buffer_insts[1].get_pin("rw")
        self.add_layout_pin("rw", rw_pin.layer, offset=rw_pin.ll(), width=rw_pin.width(),
                            height=self.height - rw_pin.by())

    def add_body_taps(self):
        # add body taps
        body_tap = pgate_tap(self.logic_buffer.logic_mod)
        for i in range(0, self.rows):
            inst = self.buffer_insts[i]
            y_offset = inst.by()
            if (i % 2) == 0:
                y_offset += self.logic_buffer.height
                mirror = "MX"
            else:
                mirror = "R0"
            self.add_inst(body_tap.name, body_tap, mirror=mirror,
                          offset=vector(inst.lx() - body_tap.width, y_offset))
            self.connect_inst([])
