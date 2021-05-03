from modules.buffer_stage import BufferStage


class WlBufferStages(BufferStage):

    def connect_inst(self, args, check=True):
        if self.insts[-1].mod == self.first_stage_mod:
            args.insert(2, "rw")
            self.copy_layout_pin(self.insts[-1], "rw")
        super().connect_inst(args, check)

    def __init__(self, first_stage_mod, buffer_stages, *args, **kwargs):
        self.first_stage_mod = first_stage_mod
        self.buffer_stages = buffer_stages
        self.inv_count = 0
        super().__init__(buffer_stages, *args, **kwargs)

    @classmethod
    def get_name(cls, first_stage_mod, buffer_stages, *args, **kwargs):
        name = BufferStage.get_name(buffer_stages[1:], *args, **kwargs)
        return first_stage_mod.name + "_" + name

    def create_buffer_inv(self, size):
        self.inv_count += 1
        if self.inv_count <= 1:
            return self.first_stage_mod

        return super(WlBufferStages, self).create_buffer_inv(size)

    def add_pins(self):
        self.add_pin_list(["in", "rw", "out_inv", "out", "vdd", "gnd"])
