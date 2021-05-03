from modules.logic_buffer import LogicBuffer

from modules.shared_decoder.one_t_one_s.wl_buffer_stages import WlBufferStages


class WlLogicBuffer(LogicBuffer):
    def __init__(self, first_stage_mod, buffer_stages, logic, *args, **kwargs):
        self.first_stage_mod = first_stage_mod
        super().__init__(buffer_stages, logic, *args, **kwargs)

    def connect_inst(self, args, check=True):
        if args[0] == "logic_out":
            args.insert(1, "rw")
        super().connect_inst(args, check)

    def add_pins(self):
        super().add_pins()
        self.add_pin("rw")

    @classmethod
    def get_name(cls, first_stage_mod, buffer_stages, logic, *args, **kwargs):
        name = super().get_name(buffer_stages[1:], logic, *args, **kwargs)
        return first_stage_mod.name + "_" + name

    def create_buffer_mod(self):
        self.buffer_mod = WlBufferStages(self.first_stage_mod, self.buffer_stages,
                                         height=self.height,
                                         route_outputs=self.route_outputs,
                                         contact_pwell=self.contact_pwell,
                                         contact_nwell=self.contact_nwell,
                                         align_bitcell=self.align_bitcell)
        self.add_mod(self.buffer_mod)

    def route_input_pins(self):
        super().route_input_pins()
        self.copy_layout_pin(self.buffer_inst, "rw")
