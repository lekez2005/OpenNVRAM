from importlib import reload

import debug
from base.contact import m1m2
from base.design import design
from base.vector import vector
from modules.buffer_stage import BufferStage


class FlopBuffer(design):
    """
    Flop a signal and buffer given input buffer sizes
    """

    def __init__(self, flop_module_name, buffer_stages):

        if buffer_stages is None or len(buffer_stages) < 1:
            debug.error("There should be at least one buffer stage", 1)

        self.buffer_stages = buffer_stages

        self.flop_module_name = flop_module_name

        name = "flop_buffer_{}".format("_".join(
            ["{:.3g}".format(x).replace(".", "_") for x in buffer_stages]))

        super().__init__(name=name)

        self.create_layout()

    def create_layout(self):
        self.add_pins()
        self.create_modules()
        self.add_modules()
        self.width = self.buffer_inst.rx()
        self.fill_layers()
        self.add_layout_pins()

    def add_pins(self):
        self.add_pin_list(["din", "clk", "dout", "vdd", "gnd"])

    def create_modules(self):

        self.flop = self.create_mod_from_str(self.flop_module_name)

        self.height = self.flop.height

        self.buffer = BufferStage(self.buffer_stages, height=self.height, route_outputs=False,
                                  contact_pwell=False, contact_nwell=False, align_bitcell=False)
        self.add_mod(self.buffer)

    def add_modules(self):
        self.flop_inst = self.add_inst("flop", mod=self.flop, offset=vector(0, 0))
        self.connect_inst(["din", "flop_out", "flop_out_bar", "clk", "vdd", "gnd"])

        poly_dummies = self.flop.get_gds_layer_rects("po_dummy", "po_dummy", recursive=True)
        right_most = max(poly_dummies, key=lambda x: x.rx())
        center_poly = 0.5*(right_most.lx() + right_most.rx())
        x_space = center_poly - self.flop.width

        self.buffer_inst = self.add_inst("buffer", mod=self.buffer, offset=self.flop_inst.lr() + vector(x_space, 0))

        if len(self.buffer_stages) % 2 == 0:
            nets = ["flop_out", "dout_bar", "dout"]
            flop_out = self.flop_inst.get_pin("dout")
            path_start = vector(flop_out.rx(), flop_out.uy() - 0.5 * self.m2_width)
        else:
            nets = ["flop_out_bar", "dout", "dout_bar"]
            flop_out = self.flop_inst.get_pin("dout_bar")
            path_start = vector(flop_out.rx(), flop_out.uy() - 0.5 * self.m2_width)

        self.connect_inst(nets + ["vdd", "gnd"])

        buffer_in = self.buffer_inst.get_pin("in")
        mid_x = 0.5*(buffer_in.lx() + flop_out.rx())
        self.add_path("metal2", [path_start, vector(mid_x, path_start[1]), buffer_in.lc()])

        self.add_contact(m1m2.layer_stack, offset=vector(buffer_in.lx()+m1m2.second_layer_height,
                                                         buffer_in.cy()-0.5*m1m2.second_layer_width),
                         rotate=90)

    def fill_layers(self):
        inverter = self.buffer.module_insts[0].mod
        layers = ["nwell", "nimplant", "pimplant"]
        purposes = ["drawing", "drawing", "drawing"]
        for i in range(len(layers)):
            layer = layers[i]
            inv_layer = inverter.get_layer_shapes(layer, purposes[i])[0]
            flop_layers = self.flop.get_gds_layer_rects(layer, purposes[i],
                                                        recursive=True)
            rightmost = max(flop_layers, key=lambda x: x.rx())

            # there could be multiple implants, one for the tx and one for the tap
            if "implant" in layer:
                all_right_rects = list(filter(lambda x: x.rx() == rightmost.rx(), flop_layers))
                # find the closest one to the middle
                rightmost = max(all_right_rects, key=lambda x: x.height)
                tap_rect = min(all_right_rects, key=lambda x: x.height)
                # add tap rect
                left = rightmost.rx()
                # leave space to avoid spacing issues with adjacent modules
                implant_space = self.get_space_by_width_and_length(layer)
                right = inv_layer.rx() + self.buffer_inst.lx() - implant_space
                self.add_rect(layer, offset=vector(left, tap_rect.by()), width=right - left,
                              height=tap_rect.height)

            top = min(inv_layer.uy(), rightmost.uy())
            left = rightmost.rx()
            right = inv_layer.lx() + self.buffer_inst.lx()
            bottom = max(inv_layer.by(), rightmost.by())
            width = right - left
            if width > 0:
                self.add_rect(layer, offset=vector(left, bottom), width=right - left,
                              height=top - bottom)

    def add_layout_pins(self):
        for pin_name in ["vdd", "gnd"]:
            buffer_pin = self.buffer_inst.get_pin(pin_name)
            flop_pin = self.flop_inst.get_pin(pin_name)
            if pin_name == "gnd":
                y_offset = max(buffer_pin.by(), flop_pin.by())
                y_top = min(buffer_pin.uy(), flop_pin.uy())
            else:
                y_offset = max(buffer_pin.by(), flop_pin.by())
                y_top = min(buffer_pin.uy(), flop_pin.uy())
            self.add_layout_pin(pin_name, buffer_pin.layer, offset=vector(0, y_offset), width=self.width,
                                height=y_top - y_offset)
        self.copy_layout_pin(self.flop_inst, "clk", "clk")
        self.copy_layout_pin(self.flop_inst, "din", "din")
        if len(self.buffer_stages) == 1:
            flop_out = "out_inv"
        else:
            flop_out = "out"
        self.copy_layout_pin(self.buffer_inst, flop_out, "dout")
