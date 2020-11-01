from base.design import design
from base.hierarchy_layout import GDS_ROT_90, GDS_ROT_180, GDS_ROT_270
from base.vector import vector


class DrcRotationWrapper(design):
    def __init__(self, child_mod, rotation_angle: str):
        assert rotation_angle in [GDS_ROT_90, GDS_ROT_180, GDS_ROT_270]
        name = child_mod.name + "_rot"
        super().__init__(name)
        self.add_inst("child_mod", mod=child_mod, offset=vector(child_mod.height, 0),
                      rotate=rotation_angle)
