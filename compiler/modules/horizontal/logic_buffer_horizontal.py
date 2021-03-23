from modules.logic_buffer import LogicBuffer
from modules.horizontal.buffer_stages_horizontal import BufferStagesHorizontal
from modules.horizontal.pnand2_horizontal import pnand2_horizontal
from modules.horizontal.pnand3_horizontal import pnand3_horizontal
from modules.horizontal.pnor2_horizontal import pnor2_horizontal
from modules.horizontal.pnor3_horizontal import pnor3_horizontal

logic_mods = {
    "pnand2": pnand2_horizontal,
    "pnor2": pnor2_horizontal,
    "pnand3": pnand3_horizontal,
    "pnor3": pnor3_horizontal
}


class LogicBufferHorizontal(LogicBuffer):
    @classmethod
    def get_name(cls, buffer_stages, logic="pnand2", *args, **kwargs):
        name = "logic_buffer_{}_{}".format(logic, BufferStagesHorizontal.get_name(buffer_stages))
        return name

    def create_modules(self):
        self.route_inputs = False

        self.logic_mod = logic_mods[self.logic](size=1)
        self.add_mod(self.logic_mod)

        self.buffer_mod = BufferStagesHorizontal(self.buffer_stages)
        self.add_mod(self.buffer_mod)
