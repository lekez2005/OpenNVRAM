import design
from tech import full_stack_vias
from vector import vector


class ContactFullStack(design.design):
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


    def __init__(self, start_layer=0, centralize=True):

        name = "full_stack_via_M{}_M10".format(start_layer + 1)
        design.design.__init__(self, name)

        via_defs = full_stack_vias

        max_height = max(map(self.get_height, via_defs))

        for i in range(len(via_defs)):
            if i == 0:
                temp_start_layer = start_layer
            else:
                temp_start_layer = 0

            width, height = self.create_stack(full_stack_vias[i], max_height, centralize, temp_start_layer)
            if i == 0:
                self.first_layer_height = height
                self.first_layer_width = width
            elif i == len(via_defs) - 1:
                self.second_layer_height = height
                self.second_layer_width = width
        self.height = max_height
        self.width = max(self.first_layer_width, self.second_layer_width)

    def get_height(self, params):
        return 2 * params["enclosure"][1] + max(0, params["dimensions"][1] - 1) * params["spacing"] + params["dimensions"][1] * params["width"]

    def create_stack(self, params, height, centralize, start_layer=0):
        """min_width and min_height prevent insufficient overlap in the intermediate layer between two stacks"""

        # retrieve parameters
        h_enc = params["enclosure"][0]
        spacing = params["spacing"]
        via_width = params["width"]
        dimensions = params["dimensions"]

        # calculate dimensions

        width = 2*h_enc + max(0, dimensions[0]-1)*spacing + dimensions[0]*via_width

        # create layer rects
        layers = params["layers"]
        for i in range(start_layer, len(layers)):
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
        for i in range(start_layer, len(layers)-1):
            layer = params["vias"][i]
            for row in range(dimensions[1]):
                for col in range(dimensions[0]):
                    offset = origin + (col*via_pitch, row*via_pitch)
                    self.add_rect(layer, offset, width=via_width, height=via_width)

        return width, height

