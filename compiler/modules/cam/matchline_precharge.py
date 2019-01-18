import math

import debug
from base import contact
from base import design
from base import utils
from base.vector import vector
from globals import OPTS
from pgates.ptx import ptx
from tech import layer, purpose, parameter


class matchline_precharge(design.design):

    def __init__(self, size=1):
        design.design.__init__(self, "matchline_precharge")
        debug.info(2, "Create matchline_precharge")

        c = __import__(OPTS.bitcell)
        self.mod_bitcell = getattr(c, OPTS.bitcell)
        self.bitcell = self.mod_bitcell()

        c = __import__(OPTS.ms_flop_horz_pitch)
        mod_flop_horz = getattr(c, OPTS.ms_flop_horz_pitch)
        self.ms_flop = mod_flop_horz()


        self.beta = parameter["beta"]
        self.ptx_width = size * self.beta * parameter["min_tx_size"]
        self.height = self.bitcell.height

        self.add_pins()
        self.create_layout()

    def add_pins(self):
        self.add_pin_list(["chb", "ml", "vdd"])

    def create_layout(self):
        self.calculate_fingers()
        self.add_tx()
        self.fill_well_implants()
        self.add_layout_pins()

    def calculate_fingers(self):
        # create big enough dummy to not have min area drc's
        dummy_ptx = ptx(width=self.height, mults=1, tx_type="pmos")
        vertical_space = dummy_ptx.implant_height - self.height + 0.5*self.implant_space
        max_tx_width = self.height - vertical_space
        self.tx_mults = int(math.ceil(self.ptx_width/max_tx_width))
        self.ptx_width = utils.ceil(self.ptx_width/self.tx_mults)

    def add_tx(self):


        self.ptx = ptx(width=self.ptx_width, mults=self.tx_mults, tx_type="pmos", connect_active=True,
                       connect_poly=True)
        self.add_mod(self.ptx)


        poly_dummies = self.ptx.get_layer_shapes("po_dummy", "po_dummy")
        left_dummy = min(poly_dummies, key=lambda x: x.offset.x)

        # the poly dummy should align with bitcell dummy
        x_offset = - left_dummy.offset.x - 0.5*self.poly_width

        # there should be line end space to vdd
        if self.tx_mults == 1:
            active_rect = self.ptx.get_layer_shapes("active")[0]
            vdd_bottom = active_rect.offset.y + active_rect.height + self.line_end_space
        else:
            vdd_bottom = self.ptx.get_pin("S").by()
        vdd_center = vdd_bottom + 0.5 * self.bitcell.get_pin("vdd").height()
        y_offset = self.height - vdd_center

        self.ptx_offset = vector(x_offset, y_offset)

        self.ptx_inst = self.add_inst("ptx", mod=self.ptx, offset=self.ptx_offset)
        self.connect_inst(["ml", "chb", "vdd", "vdd"])

    def fill_well_implants(self):
        self.extend_poly()
        self.extend_well_pimplant()

    def extend_poly(self):
        poly_rects = self.ptx.get_layer_shapes("po_dummy")
        dummy_rects = self.ptx.get_layer_shapes("po_dummy", "po_dummy")
        layer_names = ["poly"]*len(poly_rects) + ["po_dummy"]*len(dummy_rects)
        all_rects = poly_rects + dummy_rects
        for i in range(len(all_rects)):
            rect = all_rects[i]
            layer_name = layer_names[i]
            self.add_rect(layer_name, width=rect.width, offset=rect.offset + self.ptx_offset,
                          height=self.height - (rect.offset.y + self.ptx_offset.y))
        rightmost = max(dummy_rects, key=lambda x: x.offset.x)
        self.width = rightmost.offset.x + self.ptx_offset.x + 0.5 * self.poly_width

    def extend_well_pimplant(self):

        # extend gnd pin from bitcell to flop
        flop_gnd = self.ms_flop.get_pin("gnd")
        self.add_rect("metal1", offset=vector(0, flop_gnd.by()), width=self.width, height=flop_gnd.height())
        bitcell_gnd = self.bitcell.get_pin("gnd")
        self.add_rect("metal1", offset=vector(-0.5*self.rail_height, 0), height=bitcell_gnd.uy(), width=self.rail_height)


        for shape_layer in ["pimplant", "nwell"]:
            purpose_num = purpose["drawing"]
            purpose_name = "drawing"

            # left x
            bitcell_rects = self.bitcell.gds.getShapesInLayer(layer[shape_layer], purpose_num)
            rightmost = max(bitcell_rects, key=lambda x: x[1][0])[1][0]
            bitcell_top_rect = max(bitcell_rects, key=lambda x: x[1][1])[1][1]
            rect_extension = rightmost - self.bitcell.width
            left = rect_extension

            # right x
            flop_rects = self.ms_flop.gds.getShapesInLayer(layer[shape_layer], purpose_num)
            leftmost = min(flop_rects, key=lambda x: x[0][0])[0][0]
            rect_extension = leftmost
            right = self.width + rect_extension

            # bottom
            ptx_rects = self.ptx.get_layer_shapes(shape_layer, purpose=purpose_name)
            # bottom = min(min(bitcell_rects, key=lambda x: x[0][1])[0][1], ptx_rects[0].offset.y + self.ptx_offset.y)
            bottom = 0

            # top
            ptx_rect_top = ptx_rects[0].offset.y + ptx_rects[0].height + self.ptx_offset.y
            if shape_layer == "pimplant":
                top = self.height + self.ptx.implant_enclose
            elif shape_layer == "nwell":
                top = max(ptx_rect_top, flop_rects[0][1][1])
            
            top = max(top, ptx_rect_top)

            self.add_rect(shape_layer, offset=vector(left, bottom), width=right - left, height=top - bottom)



    def add_layout_pins(self):
        # vdd pin
        if self.tx_mults == 1:
            source_pin = self.ptx_inst.get_pin("S")
            self.add_rect("metal1", offset=source_pin.ul(), width=source_pin.width(),
                          height=self.height - source_pin.uy())
        vdd_height = self.bitcell.get_pin("vdd").height()
        self.add_layout_pin("vdd", "metal1", offset=vector(0, self.height - 0.5*vdd_height),
                            width=self.width, height=vdd_height)

        # ml pin
        bitcell_ml = self.bitcell.get_pin("ML")
        drain_pin = self.ptx_inst.get_pin("D")
        self.add_path("metal3", [vector(0, bitcell_ml.cy()),
                                 vector(drain_pin.lx() + 0.5*contact.m2m3.second_layer_width, bitcell_ml.cy()),
                                 drain_pin.lc()])
        self.add_contact(contact.m2m3.layer_stack,
                         offset=vector(drain_pin.lx(), drain_pin.cy() - 0.5*contact.m2m3.second_layer_height))
        self.add_layout_pin("ml", "metal3", offset=vector(0, bitcell_ml.by()), width=self.width)


        # chb pin
        gate_pin = self.ptx_inst.get_pin("G")
        rail_x = drain_pin.lx() - self.m2_width - self.wide_m1_space
        self.add_contact(contact.m1m2.layer_stack, offset=gate_pin.lc() + vector(contact.m1m2.second_layer_height,
                                                                                 -0.5*contact.m1m2.second_layer_width),
                         rotate=90)
        self.add_rect("metal2", offset=vector(rail_x, gate_pin.cy() - 0.5*contact.m1m2.second_layer_width),
                      width=gate_pin.lx() - rail_x)
        self.add_layout_pin("chb", "metal2", offset=vector(rail_x, 0), height=self.height)
        # add fill for single finger
        if self.tx_mults == 1:
            fill_height = gate_pin.height()
            fill_width = utils.ceil(self.minarea_metal1_contact/fill_height)
            self.add_rect("metal1", offset=vector(gate_pin.lx() + contact.m1m2.second_layer_height - fill_width,
                                                  gate_pin.by()), height=fill_height, width=fill_width)




