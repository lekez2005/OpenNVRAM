import copy
import math

from base import design, utils
from base.vector import vector
from tech import full_stack_vias
from base import unique_meta


class ContactFullStack(design.design, metaclass=unique_meta.Unique):
    """
    Object for a full metal stack power
    """
    _m1_stack = None
    _m2_stack = None

    @classmethod
    def m1mtop(cls):
        if cls._m1_stack is None:
            cls._m1_stack = cls(start_layer=0, centralize=False)
        return cls._m1_stack

    @classmethod
    def m2mtop(cls):
        if cls._m2_stack is None:
            cls._m2_stack = cls(start_layer=1)
        return cls._m2_stack

    @classmethod
    def get_name(cls, start_layer=0, stop_layer=-1, centralize=True, dimensions=None, max_width=None):

        dim_str = "_".join([str(item) for sublist in dimensions for item in sublist]) if dimensions else ""
        width_suffix = "" if not max_width else "_w{:.5g}".format(max_width).replace(".", "__")
        alignment = "c" if centralize else "l"
        metal_layers, layer_numbers = utils.get_sorted_metal_layers()
        stop_layer_name = metal_layers[stop_layer]
        start_layer_name = metal_layers[start_layer]
        name = "full_stack_via_{}_{}_{}_{}{}".format(start_layer_name, stop_layer_name, alignment,
                                                     dim_str, width_suffix)
        return name

    def __init__(self, start_layer=0, stop_layer=-1, centralize=True, dimensions=None, max_width=None):
        dimensions = dimensions if dimensions else []
        design.design.__init__(self, self.name)

        via_defs = copy.deepcopy(full_stack_vias)
        for i in range(len(dimensions)):
            via_defs[i]["dimensions"] = dimensions[i]

        metal_layers, layer_numbers = utils.get_sorted_metal_layers()
        real_start_layer = layer_numbers[start_layer] - 1
        real_stop_layer = layer_numbers[stop_layer] - 1

        # Remove unused layers and vias
        for via_def in via_defs:
            new_vias = []
            new_layers = []
            last_layer = None
            for i in range(len(via_def["vias"])):
                bottom_layer_num = int(via_def["layers"][i][5:])
                if real_start_layer < bottom_layer_num <= real_stop_layer:
                    new_vias.append(via_def["vias"][i])
                    new_layers.append(via_def["layers"][i])
                    last_layer = via_def["layers"][i + 1]
            if last_layer is not None:
                new_layers.append(last_layer)
            via_def["vias"] = new_vias
            via_def["layers"] = new_layers

        via_defs = [via_def for via_def in via_defs if len(via_def["vias"]) > 0]
        assert len(via_defs) > 0, "Invalid start and stop layers: {}, {}".format(start_layer, stop_layer)
        if max_width is not None:
            bottom_via_def = via_defs[0]
            via_pitch = bottom_via_def["width"] + bottom_via_def["spacing"]
            total_enclosure = 2 * bottom_via_def["enclosure"][0] + bottom_via_def["width"]
            num_vias = 1 + math.floor((max_width - total_enclosure) / via_pitch)
            bottom_via_def["dimensions"] = [num_vias, bottom_via_def["dimensions"][1]]

        max_height = max(map(self.get_height, via_defs))

        for i in range(len(via_defs)):
            temp_start_layer = 0
            temp_stop_layer = -1

            width, height = self.create_stack(via_defs[i], max_height, centralize, temp_start_layer, temp_stop_layer)
            if i == 0:
                self.first_layer_height = height
                self.first_layer_width = width
            if i == len(via_defs) - 1:
                self.second_layer_height = height
                self.second_layer_width = width
        self.height = max_height
        self.width = max(self.first_layer_width, self.second_layer_width)

    def get_height(self, params):
        return 2 * params["enclosure"][1] + max(0, params["dimensions"][1] - 1) * params["spacing"] + params["dimensions"][1] * params["width"]

    def create_stack(self, params, height, centralize, start_layer=0, stop_layer=-1):
        """min_width and min_height prevent insufficient overlap in the intermediate layer between two stacks"""
        layers = params["layers"]
        if stop_layer < 0:
            stop_layer = len(layers) - 1

        # retrieve parameters
        h_enc = params["enclosure"][0]
        spacing = params["spacing"]
        via_width = params["width"]
        dimensions = params["dimensions"]

        # calculate dimensions

        width = 2*h_enc + max(0, dimensions[0]-1)*spacing + dimensions[0]*via_width

        # create layer rects

        for i in range(start_layer, stop_layer + 1):
            x_offset = -0.5*width if centralize else 0
            self.add_rect(layers[i], vector(x_offset, 0), width=width, height=height)

        # create via layers
        via_left_to_right = max(0, dimensions[0] - 1) * spacing + dimensions[0] * via_width
        via_top_to_bottom = max(0, dimensions[1] - 1) * spacing + dimensions[1] * via_width

        full_v_enc = height - via_top_to_bottom
        if centralize:
            origin = vector(-via_left_to_right * 0.5, 0.5 * full_v_enc)
        else:
            origin = vector((width-via_left_to_right)*0.5, 0.5 * full_v_enc)

        via_pitch = spacing + via_width
        for i in range(start_layer, stop_layer):
            layer = params["vias"][i]
            for row in range(dimensions[1]):
                for col in range(dimensions[0]):
                    offset = origin + (col*via_pitch, row*via_pitch)
                    self.add_rect(layer, offset, width=via_width, height=via_width)

        return width, height

