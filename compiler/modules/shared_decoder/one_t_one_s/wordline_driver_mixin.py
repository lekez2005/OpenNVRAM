from base.design import design
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.shared_decoder.one_t_one_s.wl_logic_buffer import WlLogicBuffer
from pgates.pgate_tap import pgate_tap


@library_import
class PinvWl(design):
    """
    Read WordLine Driver control circuit: Special Inverter
    """

    pin_names = ["A", "Z", "RW", "vdd", "gnd"]


class wordline_driver_mixin():
    def connect_inst(self, args, check=True):
        if self.insts[-1].mod == self.logic_buffer:
            args.append("rw")
        super().connect_inst(args, check)

    def add_pins(self):
        super().add_pins()
        self.add_pin("rw")

    def get_pgate_height(self):
        bitcell = self.create_mod_from_str_(OPTS.bitcell)
        return bitcell.height

    def create_modules(self):
        if self.name == "rwl_driver":
            mod_name = OPTS.rwl_inverter_mod
        else:
            mod_name = OPTS.wwl_inverter_mod
        first_stage_mod = PinvWl(mod_name=mod_name)
        self.logic_buffer = WlLogicBuffer(first_stage_mod=first_stage_mod,
                                          buffer_stages=self.buffer_stages,
                                          logic="pnand2",
                                          height=self.get_pgate_height(),
                                          route_outputs=False,
                                          route_inputs=False,
                                          contact_pwell=False, contact_nwell=False,
                                          align_bitcell=True)
        self.add_mod(self.logic_buffer)

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
