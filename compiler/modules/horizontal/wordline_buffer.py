from base.design import METAL1
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from globals import OPTS
from modules.buffer_stage import BufferStage
from modules.horizontal.wordline_inverter import wordline_inverter


class wordline_buffer(BufferStage):
    rotation_for_drc = GDS_ROT_270

    @classmethod
    def get_name(cls, buffer_stages, *args, **kwargs):
        name = "wordline_buffer_" + "_".join(['{:.3g}'.format(x) for x in buffer_stages])
        return name.replace(".", "__")

    def create_layout(self):
        super().create_layout()
        self.width = self.module_insts[-1].rx()
        self.add_boundary()

    def create_buffer_inv(self, size):
        index = self.buffer_stages.index(size)
        mirror = index % 2 == 1
        beta = OPTS.wordline_beta[index]
        inv = wordline_inverter(size=size, beta=beta, mirror=mirror)
        self.height = inv.height
        return inv

    def join_a_z_pins(self, a_pin, z_pin):
        y_offset = z_pin.cy() - 0.5 * self.m1_width
        self.add_rect(METAL1, offset=vector(z_pin.rx(), y_offset),
                      width=a_pin.lx() + self.m1_width - z_pin.rx())
        self.add_rect(METAL1, offset=vector(a_pin.lx(), y_offset),
                      height=a_pin.cy() - y_offset)
