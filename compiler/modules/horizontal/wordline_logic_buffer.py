from base.design import METAL1
from base.vector import vector
from modules.horizontal.pnand2_wordline import pnand2_wordline, pnor3_wordline, pnand3_wordline, pnor2_wordline
from modules.horizontal.wordline_buffer import WordlineBuffer
from modules.logic_buffer import LogicBuffer

logic_mods = {
    "pnand2": pnand2_wordline,
    "pnor2": pnor2_wordline,
    "pnand3": pnand3_wordline,
    "pnor3": pnor3_wordline
}


class WordlineLogicBuffer(LogicBuffer):
    @classmethod
    def get_name(cls, buffer_stages, logic="pnand2", *args, **kwargs):
        name = "wordline_logic_buffer_{}_{}".format(logic,
                                                    WordlineBuffer.get_name(buffer_stages))
        return name

    def create_modules(self):
        self.route_inputs = False

        self.logic_mod = logic_mods[self.logic](size=1, mirror=True)
        self.add_mod(self.logic_mod)

        self.buffer_mod = WordlineBuffer(self.buffer_stages, route_outputs=False)
        self.add_mod(self.buffer_mod)

    def join_logic_out_to_buffer_in(self, logic_out, buffer_in):
        self.add_path(METAL1, [logic_out.rc() - vector(0.5 * self.m1_width, 0), buffer_in.lc()])
