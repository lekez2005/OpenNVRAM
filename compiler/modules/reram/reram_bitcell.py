from base.design import design, METAL1
from base.unique_meta import Unique
from base.vector import vector


class reram_bitcell(design, metaclass=Unique):
    """Placeholder bitcell"""
    @classmethod
    def get_name(cls):
        return "reram_bitcell"

    def __init__(self):
        design.__init__(self, self.get_name())
        self.width = 2.5
        # self.width = 2.28
        self.height = 2.7
        self.add_pin_list(["BL", "BR", "WL", "gnd"])

        x_offsets = [0.17 * self.width, 0.85 * self.width,
                     0.1 * self.width, 0.9 * self.width]
        for i, pin_name in enumerate(self.pins):
            self.add_layout_pin(pin_name, METAL1, offset=vector(x_offsets[i], 0))
        self.add_boundary()
