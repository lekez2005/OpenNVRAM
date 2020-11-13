from modules.buffer_stage import BufferStage
from modules.push_rules.pinv_horizontal import pinv_horizontal


class BufferStagesHorizontal(BufferStage):

    @classmethod
    def get_name(cls, buffer_stages, *args, **kwargs):
        name = "buffer_stage_" + "_".join(['{:.3g}'.format(x) for x in buffer_stages])
        return name.replace(".", "__")

    def create_buffer_inv(self, size):
        self.route_outputs = False
        inv = pinv_horizontal(size=size)
        self.height = inv.height
        return inv
