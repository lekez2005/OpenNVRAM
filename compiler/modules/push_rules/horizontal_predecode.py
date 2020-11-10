from abc import ABC

from base import contact, utils
from base.contact import m1m2, m2m3
from base.design import PO_DUMMY, METAL1, METAL2, METAL3
from base.hierarchy_layout import GDS_ROT_90
from base.vector import vector
from globals import OPTS
from modules.hierarchical_predecode import hierarchical_predecode
from modules.push_rules.pgate_horizontal_tap import pgate_horizontal_tap
from modules.push_rules.pinv_horizontal import pinv_horizontal
from modules.push_rules.pnand2_horizontal import pnand2_horizontal
from modules.push_rules.pnand3_horizontal import pnand3_horizontal
from modules.push_rules.pnor2_horizontal import pnor2_horizontal
from modules.push_rules.pnor3_horizontal import pnor3_horizontal


class horizontal_predecode(hierarchical_predecode, ABC):
    rotation_for_drc = GDS_ROT_90
    num_inputs = 2

    def __init__(self, route_top_rail=True, use_flops=False, buffer_sizes=None, negate=False):
        hierarchical_predecode.__init__(self, self.num_inputs, route_top_rail, use_flops=use_flops,
                                        buffer_sizes=buffer_sizes, negate=negate)

        self.negate = negate

        self.add_pins()
        self.create_modules()
        self.setup_constraints()
        self.create_layout()
        self.add_boundary()
        self.DRC_LVS()

    def connect_inst(self, args, check=True):
        """Correct connections for negative outputs"""
        if self.negate and args and args[0].startswith("flop_in"):
            args[1], args[2] = args[2], args[1]
        super().connect_inst(args, check)

    def create_layout(self):
        self.create_rails()
        self.add_input_inverters()
        self.add_output_inverters()
        self.add_nand(self.get_nand_connections())
        self.route()

    def route(self):
        self.route_input_flops()
        self.route_nand_to_rails()
        self.route_output_inverters()
        self.route_vdd_gnd()

    def setup_constraints(self):
        super().setup_constraints()
        self.x_off_nand += self.m2_pitch
        self.x_off_inv_2 += self.m2_pitch

    def create_flops(self):
        self.vertical_flops = False
        if self.use_flops:
            self.flop = self.create_mod_from_str(OPTS.predecoder_flop)

    def create_modules(self):
        inverter_size = self.buffer_sizes[1]
        self.top_inv = self.inv = pinv_horizontal(size=inverter_size)
        self.add_mod(self.inv)

        nand_size = self.buffer_sizes[0]
        if self.negate:
            if self.number_of_inputs == 2:
                nand = pnor2_horizontal(size=1)
            else:
                nand = pnor3_horizontal(size=1)
        else:
            if self.number_of_inputs == 2:
                nand = pnand2_horizontal(size=nand_size)
            else:
                nand = pnand3_horizontal(size=nand_size)
        self.nand = self.top_nand = nand
        self.add_mod(nand)

        self.module_height = self.top_inv.height

        self.pgate_tap = pgate_horizontal_tap(self.inv)
        self.add_mod(self.pgate_tap)

        self.create_flops()

    def add_input_inverters(self):
        super().add_input_inverters()
        if self.use_flops:
            # add dummy poly
            dummy_fills = self.flop.get_poly_fills(self.flop.flop_mod)
            fill_x = 0.5 * self.poly_to_field_poly
            fill_width = self.in_inst[0].width - 2 * fill_x
            if not dummy_fills:
                return
            for rect in dummy_fills["right"]:
                ll, ur = map(vector, rect)
                y_offset = self.flop.flop_mod.width - ur.x
                bottom_inst = self.in_inst[0]
                self.add_rect(PO_DUMMY, offset=bottom_inst.ll() + vector(fill_x, y_offset),
                              width=fill_width, height=ur.x - ll.x)
            if len(self.in_inst) % 2 == 0:
                y_offsets = [x[0][0] - self.flop.flop_mod.width for x in dummy_fills["right"]]
            else:
                y_offsets = [-x[0][0] for x in dummy_fills["left"]]
            top_inst = self.in_inst[-1]
            for y_offset in y_offsets:
                self.add_rect(PO_DUMMY, offset=top_inst.ul() + vector(fill_x, y_offset),
                              width=fill_width, height=self.poly_width)

    def add_output_inverters(self):
        super().add_output_inverters()
        for inv_inst in self.inv_inst:
            self.add_inst(self.pgate_tap.name, self.pgate_tap,
                          offset=inv_inst.offset + vector(inv_inst.width, 0),
                          mirror=inv_inst.mirror)
            self.connect_inst([])
        self.width = self.inv_inst[0].rx() + self.pgate_tap.width

    def connect_pin_to_rail(self, rail_x, pin):

        self.add_contact_center(m2m3.layer_stack, offset=vector(rail_x, pin.cy()))

        if rail_x > pin.cx():
            via_x = pin.rx() + contact.m2m3.height
            width = max(self.metal1_minwidth_fill, rail_x - via_x)
            connect_x = rail_x - width
            self.add_rect("metal3", offset=vector(connect_x, pin.by()), width=width)
        else:
            via_x = pin.lx() + m2m3.height
            x_offset = rail_x
            width = max(pin.lx() - x_offset, self.metal1_minwidth_fill)

            self.add_rect("metal3", offset=vector(x_offset, pin.by()), width=width)
        self.add_contact(m2m3.layer_stack, offset=vector(via_x, pin.by()),
                         rotate=90)

    def route_input_flops(self):
        for row in range(self.number_of_inputs):
            # connect din
            self.connect_pin_to_rail(self.rails["flop_in[{}]".format(row)],
                                     self.in_inst[row].get_pin("din"))
            self.connect_pin_to_rail(self.rails["clk"],
                                     self.in_inst[row].get_pin("clk"))

            if self.negate:
                a = "dout_bar"
                a_bar = "dout"
            else:
                a = "dout"
                a_bar = "dout_bar"

            self.connect_pin_to_rail(self.rails["A[{}]".format(row)],
                                     self.in_inst[row].get_pin(a))
            self.connect_pin_to_rail(self.rails["Abar[{}]".format(row)],
                                     self.in_inst[row].get_pin(a_bar))

    def route_nand_to_rails(self):
        nand_input_line_combination = self.get_nand_input_line_combination()

        max_rail = max(self.rails.values())

        for k in range(self.number_of_outputs):
            index_lst = nand_input_line_combination[k]
            if self.number_of_inputs == 2:
                gate_lst = ["A", "B"]
            else:
                gate_lst = ["A", "B", "C"]

            nand_inst = self.nand_inst[k]

            rail_pitch = m1m2.height + self.get_line_end_space(METAL1)

            y_offsets = {"A": nand_inst.cy(),
                         "B": nand_inst.cy() - rail_pitch,
                         "C": nand_inst.cy() + rail_pitch
                         }

            for rail_pin, gate_pin_name in zip(index_lst, gate_lst):
                y_offset = y_offsets[gate_pin_name]
                nand_pin = nand_inst.get_pin(gate_pin_name)
                rail_x = self.rails[rail_pin]
                self.add_contact_center(m1m2.layer_stack, offset=vector(rail_x, y_offset))

                if gate_pin_name == "A":
                    self.add_rect(METAL1, offset=vector(rail_x, y_offset - 0.5 * self.m1_width),
                                  width=nand_pin.lx() - rail_x)
                else:
                    via_x = max_rail + self.m2_pitch + 0.5 * m1m2.width
                    width = via_x - rail_x
                    if width < self.metal1_minwidth_fill:
                        x_offset = via_x - width
                        if (rail_x - 0.5 * self.m1_width - x_offset) < self.m1_width:
                            x_offset = rail_x - 1.5 * self.m1_width
                        width = via_x - x_offset
                    else:
                        x_offset = via_x - width
                    self.add_rect(METAL1, offset=vector(x_offset, y_offset - 0.5 * self.m1_width),
                                  width=width)
                    self.add_contact_center(m1m2.layer_stack, offset=vector(via_x, y_offset))

                    self.add_rect(METAL2, offset=vector(via_x, y_offset - 0.5 * self.m2_width),
                                  width=nand_pin.cx() - via_x)
                    self.add_contact_center(m1m2.layer_stack, offset=vector(nand_pin.cx(), y_offset))

                y_offset += rail_pitch

    def route_output_inverters(self):
        """
        Route all conections of the outputs inverters
        """
        for num in range(self.number_of_outputs):
            # route nand output to output inv input
            z_pin = self.nand_inst[num].get_pin("Z")
            a_pin = self.inv_inst[num].get_pin("A")
            self.add_rect("metal1", offset=z_pin.rc(), width=a_pin.cx() - z_pin.rx())

            self.copy_layout_pin(self.inv_inst[num], "Z", "out[{}]".format(num))

    def route_vdd_gnd(self):
        for i in range(len(self.in_inst) + 1, self.number_of_outputs):
            nand_inst = self.nand_inst[i]
            for pin_name in ["vdd", "gnd"]:
                pin = nand_inst.get_pin(pin_name)
                self.add_layout_pin(pin_name, pin.layer, offset=pin.ll(),
                                    height=pin.height(), width=self.width - pin.lx())
        # flop power to nand power
        for i in range(len(self.in_inst)):
            for pin_name in ["vdd", "gnd"]:
                flop_pin = self.in_inst[i].get_pin(pin_name)
                nand_pin = self.nand_inst[i].get_pin(pin_name)
                self.add_rect(METAL3, offset=flop_pin.lr(), height=flop_pin.height(),
                              width=nand_pin.lx() + m1m2.height - flop_pin.rx())
                via_offset = vector(nand_pin.lx() + 0.5 * m1m2.height, nand_pin.cy())
                self.add_contact_center(m1m2.layer_stack, offset=via_offset, rotate=90)

                self.add_contact_center(m2m3.layer_stack, offset=via_offset, rotate=90)

                fill_height = nand_pin.height()
                fill_width = max(utils.ceil(self.minarea_metal1_contact / fill_height),
                                 m1m2.height)
                self.add_rect_center(METAL2, offset=via_offset, width=fill_width,
                                     height=fill_height)
                self.copy_layout_pin(self.in_inst[i], pin_name)

    def get_nand_connections(self):
        raise NotImplementedError
