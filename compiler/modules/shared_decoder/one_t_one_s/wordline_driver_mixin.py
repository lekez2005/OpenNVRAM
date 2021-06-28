from base.design import design
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.shared_decoder.one_t_one_s.wl_logic_buffer import WlLogicBuffer
from pgates.pgate_tap import pgate_tap

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from modules.wordline_driver_array import wordline_driver_array
else:
    class wordline_driver_array:
        pass

@library_import
class PinvWl(design):
    """
    Read WordLine Driver control circuit: Special Inverter
    """

    pin_names = ["A", "Z", "RW", "vdd", "gnd"]
    tx_mults = 1


class wordline_driver_mixin(wordline_driver_array):
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
        self.bitcell = self.create_mod_from_str(OPTS.bitcell)
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
