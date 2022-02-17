from base.design import METAL1
from globals import OPTS
from modules.mram.one_t_one_s.bl_br_reset import BlBrReset
from modules.precharge import precharge_tap
from modules.precharge_array import precharge_array


class ResetTap(precharge_tap):
    def create_layout(self):
        body_tap = self.create_mod_from_str_(OPTS.body_tap)
        self.width = body_tap.width
        self.add_well_tap()

    def join_m1_vdd(self, well_cont):
        m1_rect = well_cont.get_layer_shapes(METAL1)[0]
        self.add_rect(METAL1, m1_rect.ul(), width=m1_rect.width,
                      height=self.height - m1_rect.uy())


class BlBrResetArray(precharge_array):

    def add_pins(self):
        for i in range(self.columns):
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))
        self.add_pin_list(self.pc_cell.pins[2:])

    def get_connections(self, col):
        return f"bl[{col}] br[{col}]".split() + self.pc_cell.pins[2:]

    def create_modules(self):
        self.pc_cell = self.create_mod_from_str(OPTS.br_precharge, size=self.size)
        self.child_mod = self.pc_cell

        if OPTS.use_x_body_taps:
            self.body_tap = ResetTap(self.pc_cell, name="bl_br_tap")
            self.add_mod(self.body_tap)

    def create_layout(self):
        self.add_insts()
        self.add_dummy_poly(self.pc_cell, self.child_insts, words_per_row=1)
        for pin_name in self.pc_cell.pins[2:]:
            for pin in self.child_insts[0].get_pins(pin_name):
                self.add_layout_pin(pin_name, pin.layer, pin.ll(), height=pin.height(),
                                    width=self.width - pin.lx())
