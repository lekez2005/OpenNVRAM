from abc import ABC
from itertools import groupby
from typing import List

from tech import drc, spice


class RC:

    cap_scale = 1e-15

    def __init__(self, width, space, res, cap):
        """width, space in um, c in cap/um^2, r in ohm/square"""
        self.width = width
        self.space = space
        self.__cap = cap
        self.res = res

    @property
    def cap(self):
        return self.cap_scale * self.__cap


class DelayParamsBase(ABC):
    """
    The following params must be defined in concrete class
    c_drain, c_gate, r_pmos, r_nmos, r_intrinsic, beta
    """
    # example
    metal15 = [RC(0.1, 0.1, 0.1, 0.1)]
    min_width = drc["minwidth_metal1"]
    min_space = drc["metal1_to_metal1"]

    def __init__(self):
        # set default map
        for i in range(1, 5):
            layer = "metal{}".format(i)
            if not hasattr(self, layer):
                setattr(self, layer, [RC(self.min_width, self.min_space, spice["wire_unit_r"],
                                         spice["wire_unit_c"])])
        self.rc_map = {}
        for i in range(1, 20):
            layer = "metal{}".format(i)
            if hasattr(self, layer):
                layer_rc = getattr(self, layer)  # type: -> List[RC]
                layer_map = {}
                for width, width_matches in groupby(layer_rc, key=lambda x: x.width):
                    width_map = {}
                    for rc_param in width_matches:
                        width_map[rc_param.space] = rc_param
                    layer_map[width] = width_map
                self.rc_map[layer] = layer_map

    def get_rc(self, layer=None, width=None, space=None):
        if layer is None:
            layer = "metal1"
        if not width:
            width = self.min_width
        if not space:
            space = self.min_space

        rc_def = self.find_closest(layer, width, space)
        return rc_def.cap, rc_def.res

    def find_closest(self, layer, width, space) -> RC:
        layer_map = self.rc_map[layer]
        closest_width = min(layer_map.keys(), key=lambda x: abs(x - width))
        width_map = layer_map[closest_width]
        closest_space = min(width_map.keys(), key=lambda x: abs(x - space))
        return width_map[closest_space]
