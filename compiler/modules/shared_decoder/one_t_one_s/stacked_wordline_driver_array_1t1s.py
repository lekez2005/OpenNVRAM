from base.contact import cross_m2m3
from base.design import design, METAL3
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.shared_decoder.one_t_one_s.wl_logic_buffer import WlLogicBuffer
from modules.shared_decoder.stacked_wordline_driver_array import stacked_wordline_driver_array
from pgates.pgate_tap import pgate_tap


@library_import
class PinvWl(design):
    """
    Read WordLine Driver control circuit: Special Inverter
    """

    pin_names = ["A", "Z", "RW", "vdd", "gnd"]


class stacked_wordline_driver_array_1t1s(stacked_wordline_driver_array):

    def connect_inst(self, args, check=True):
        if self.insts[-1].mod == self.logic_buffer:
            args.append("rw")
        super().connect_inst(args, check)

    def add_pins(self):
        super().add_pins()
        self.add_pin("rw")

    def create_modules(self):
        bitcell = self.create_mod_from_str_(OPTS.bitcell)
        if self.name == "rwl_driver":
            mod_name = OPTS.rwl_inverter_mod
        else:
            mod_name = OPTS.wwl_inverter_mod
        first_stage_mod = PinvWl(mod_name=mod_name)
        self.logic_buffer = WlLogicBuffer(first_stage_mod=first_stage_mod,
                                          buffer_stages=self.buffer_stages,
                                          logic="pnand2",
                                          height=2 * bitcell.height, route_outputs=False,
                                          route_inputs=False,
                                          contact_pwell=False, contact_nwell=False,
                                          align_bitcell=True)
        self.add_mod(self.logic_buffer)

    def add_modules(self):
        super().add_modules()
        rw_pin = self.buffer_insts[1].get_pin("rw")
        self.add_layout_pin("rw", rw_pin.layer, offset=rw_pin.ll(), width=rw_pin.width(),
                            height=self.height - rw_pin.by())

        # align joining rail with in[0]
        y_offset = self.buffer_insts[0].get_pin("vdd").uy()
        rw_left = self.buffer_insts[0].get_pin("rw")

        for pin in [rw_pin, rw_left]:
            self.add_cross_contact_center(cross_m2m3, vector(pin.cx(),
                                                             y_offset + 0.5 * self.m3_width))

        self.add_rect(METAL3, offset=vector(rw_pin.cx(), y_offset),
                      width=rw_left.cx() - rw_pin.cx(), height=self.m3_width)

    def add_body_taps(self):
        # add body taps
        body_tap = pgate_tap(self.logic_buffer.logic_mod)
        for i in range(0, self.rows, 2):
            inst = self.buffer_insts[i]
            y_offset = inst.by()
            if (i % 4) < 2:
                y_offset += self.logic_buffer.height
                mirror = "MX"
            else:
                mirror = "R0"
            self.add_inst(body_tap.name, body_tap, mirror=mirror,
                          offset=vector(inst.lx() - body_tap.width, y_offset))
            self.connect_inst([])
