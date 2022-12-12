from base.design import design
from base.hierarchy_layout import GDS_ROT_270
from base.library_import import library_import
from base.unique_meta import Unique
from base.vector import vector


@library_import
class ms_flop_horz_push(design):
    pin_names = "din dout dout_bar clk vdd gnd".split()
    lib_name = "push_rules/ms_flop_horz_push"


class ms_flop_horz_push_rot(design, metaclass=Unique):
    @classmethod
    def get_name(cls):
        return "ms_flop_horz_push_rot"

    def __init__(self):
        super().__init__(self.get_name())
        mod = ms_flop_horz_push()
        self.flop_mod = mod
        self.add_mod(mod)
        mod_inst = self.add_inst("flop", mod=mod, offset=vector(0, mod.width),
                                 rotate=GDS_ROT_270)
        self.connect_inst(mod.pins)

        self.add_pin_list("din dout dout_bar clk vdd gnd".split())
        for pin in mod.pins:
            self.copy_layout_pin(mod_inst, pin, pin)

        self.width = mod.height
        self.height = mod.width
