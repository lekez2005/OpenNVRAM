from base.design import design, METAL1
from base.vector import vector


class reram_bitcell(design):
    """Placeholder bitcell"""

    def __init__(self):
        design.__init__(self, "reram_bitcell")
        self.width = 2.5
        self.height = 2.7
        self.add_pin_list(["BL", "SL", "WL", "gnd"])
        space = self.get_wide_space(METAL1) + self.m1_width
        for i, pin_name in enumerate(self.pins):
            self.add_layout_pin(pin_name, METAL1, offset=vector(i * space, 0))
        self.add_boundary()
