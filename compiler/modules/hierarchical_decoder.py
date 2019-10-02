import math

import debug
from base import contact
from base import design
from base import utils
from base.vector import vector
from globals import OPTS
from modules.hierarchical_predecode2x4 import hierarchical_predecode2x4 as pre2x4
from modules.hierarchical_predecode3x8 import hierarchical_predecode3x8 as pre3x8
from pgates.pinv import pinv
from pgates.pnand2 import pnand2
from pgates.pnand3 import pnand3
from tech import drc


class hierarchical_decoder(design.design):
    """
    Dynamically generated hierarchical decoder.
    """

    def __init__(self, rows):
        design.design.__init__(self, "hierarchical_decoder_{0}rows".format(rows))

        c = __import__(OPTS.bitcell)
        self.mod_bitcell = getattr(c, OPTS.bitcell)
        self.bitcell_height = self.mod_bitcell.height

        self.use_flops = OPTS.decoder_flops
        if self.use_flops:
            self.predec_in = "flop_in[{}]"
        else:
            self.predec_in = "in[{}]"

        self.pre2x4_inst = []
        self.pre3x8_inst = []

        self.rows = rows
        self.num_inputs = int(math.log(self.rows, 2))
        (self.no_of_pre2x4,self.no_of_pre3x8)=self.determine_predecodes(self.num_inputs)
        
        self.create_layout()
        self.DRC_LVS()

    def create_layout(self):
        self.add_modules()
        self.setup_layout_constants()
        self.add_pins()
        self.create_pre_decoder()
        self.create_row_decoder()
        self.create_vertical_rail()
        self.route_vdd_gnd()

    def add_modules(self):
        self.inv = pinv(align_bitcell=True)
        self.add_mod(self.inv)
        self.nand2 = pnand2(align_bitcell=True)
        self.add_mod(self.nand2)
        self.nand3 = pnand3(align_bitcell=True)
        self.add_mod(self.nand3)

        # CREATION OF PRE-DECODER
        self.pre2_4 = pre2x4(route_top_rail=False, use_flops=self.use_flops)
        self.add_mod(self.pre2_4)
        self.pre3_8 = pre3x8(route_top_rail=False, use_flops=self.use_flops)
        self.add_mod(self.pre3_8)

    def determine_predecodes(self,num_inputs):
        """Determines the number of 2:4 pre-decoder and 3:8 pre-decoder
        needed based on the number of inputs"""
        if (num_inputs == 2):
            return (1,0)
        elif (num_inputs == 3):
            return(0,1)
        elif (num_inputs == 4):
            return(2,0)
        elif (num_inputs == 5):
            return(1,1)
        elif (num_inputs == 6):
            return(3,0)
        elif (num_inputs == 7):
            return(2,1)
        elif (num_inputs == 8):
            return(1,2)
        elif (num_inputs == 9):
            return(0,3)
        else:
            debug.error("Invalid number of inputs for hierarchical decoder",-1)

    def setup_layout_constants(self):
        # Vertical metal rail gap definition
        self.metal2_pitch = contact.m1m2.second_layer_width + self.parallel_line_space

        self.predec_groups = []  # This array is a 2D array.

        # Distributing vertical rails to different groups. One group belongs to one pre-decoder.
        # For example, for two 2:4 pre-decoder and one 3:8 pre-decoder, we will
        # have total 16 output lines out of these 3 pre-decoders and they will
        # be distributed as [ [0,1,2,3] ,[4,5,6,7], [8,9,10,11,12,13,14,15] ]
        # in self.predec_groups
        index = 0
        for i in range(self.no_of_pre2x4):
            lines = []
            for j in range(4):
                lines.append(index)
                index = index + 1
            self.predec_groups.append(lines)

        for i in range(self.no_of_pre3x8):
            lines = []
            for j in range(8):
                lines.append(index)
                index = index + 1
            self.predec_groups.append(lines)

        self.calculate_dimensions()

        
    def add_pins(self):
        """ Add the module pins """
        
        for i in range(self.num_inputs):
            self.add_pin("A[{0}]".format(i))

        for j in range(self.rows):
            self.add_pin("decode[{0}]".format(j))
        if self.use_flops:
            self.add_pin("clk")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def calculate_dimensions(self):
        """ Calculate the overal dimensions of the hierarchical decoder """

        # If we have 4 or fewer rows, the predecoder is the decoder itself
        if self.num_inputs>=4:
            self.total_number_of_predecoder_outputs = 4*self.no_of_pre2x4 + 8*self.no_of_pre3x8
        else:
            self.total_number_of_predecoder_outputs = 0            
            debug.error("Not enough rows for a hierarchical decoder. Non-hierarchical not supported yet.",-1)

        # Calculates height and width of pre-decoder,
        if(self.no_of_pre3x8 > 0):
            self.predecoder_width = self.pre3_8.width 
        else:
            self.predecoder_width = self.pre2_4.width

        self.predecoder_height = self.pre2_4.height*self.no_of_pre2x4 + self.pre3_8.height*self.no_of_pre3x8


        # Calculates height and width of row-decoder 
        if (self.num_inputs == 4 or self.num_inputs == 5):
            nand_width = self.nand2.width
        else:
            nand_width = self.nand3.width 
        self.routing_width = self.metal2_pitch*self.total_number_of_predecoder_outputs
        self.row_decoder_width = nand_width  + self.routing_width + self.inv.width
        self.row_decoder_height = self.inv.height * self.rows

        # Calculates height and width of hierarchical decoder 
        self.height = self.predecoder_height + self.row_decoder_height
        self.width = self.predecoder_width + self.routing_width

    def create_pre_decoder(self):
        """ Creates pre-decoder and places labels input address [A] """
        
        for i in range(self.no_of_pre2x4):
            self.add_pre2x4(i)
            
        for i in range(self.no_of_pre3x8):
            self.add_pre3x8(i)
        if self.use_flops:
            if len(self.pre2x4_inst) > 0:
                predecoder = self.pre2x4_inst[0]
                if len(self.pre3x8_inst) > 0:
                    top_pin = self.pre3x8_inst[0].get_pin("clk")
                    bot_pin = self.pre2x4_inst[-1].get_pin("clk")
                    self.add_rect("metal2", offset=vector(bot_pin.ul() - vector(0, self.m2_width)),
                                  width=top_pin.rx() - bot_pin.lx())
                    self.add_rect("metal2", offset=vector(top_pin.lx(), bot_pin.uy()),
                                  height=top_pin.by() - bot_pin.uy())
                if len(self.pre3x8_inst) > 0:
                    clk_pin = self.pre3x8_inst[0].get_pin("clk")
                    self.add_layout_pin(text="clk", layer="metal2", offset=clk_pin.ll(),
                                  height=self.pre3x8_inst[-1].get_pin("clk").uy() - clk_pin.by())

                if len(self.pre2x4_inst) > 1:  # connect the clk rails
                    clk_pin = self.pre2x4_inst[0].get_pin("clk")
                    self.add_rect("metal2", offset=clk_pin.ul(),
                                  height=self.pre2x4_inst[-1].get_pin("clk").uy() - clk_pin.uy())
            else:
                predecoder = self.pre3x8_inst[0]
                if len(self.pre3x8_inst) > 0:
                    clk_pin = predecoder.get_pin("clk")
                    self.add_rect("metal2", offset=clk_pin.ul(),
                                  height=self.pre3x8_inst[-1].get_pin("clk").by() - clk_pin.uy())
            self.copy_layout_pin(predecoder, "clk", "clk")

    def add_pre2x4(self,num):
        """ Add a 2x4 predecoder """
        
        if (self.num_inputs == 2):
            base = vector(self.routing_width,0)
            mirror = "RO"
            index_off1 = index_off2 = 0
        else:
            base= vector(self.routing_width+self.pre2_4.width, num * self.pre2_4.height)
            mirror = "MY"
            index_off1 = num * 2
            index_off2 = num * 4

        pins = []
        for input_index in range(2):
            pins.append("A[{0}]".format(input_index + index_off1))
        for output_index in range(4):
            pins.append("out[{0}]".format(output_index + index_off2))
        if self.use_flops:
            pins.append("clk")
        pins.extend(["vdd", "gnd"])

        self.pre2x4_inst.append(self.add_inst(name="pre[{0}]".format(num),
                                                 mod=self.pre2_4,
                                                 offset=base,
                                                 mirror=mirror))
        self.connect_inst(pins)

        self.add_pre2x4_pins(num)

                            

    def add_pre2x4_pins(self,num):
        """ Add the input pins to the 2x4 predecoder """

        for i in range(2):
            pin = self.pre2x4_inst[num].get_pin(self.predec_in.format(i))
            pin_offset = pin.ll()
            
            pin = self.pre2_4.get_pin(self.predec_in.format(i))
            self.add_layout_pin(text="A[{0}]".format(i + 2*num ),
                                layer="metal2", 
                                offset=pin_offset,
                                width=pin.width(),
                                height=pin.height())

        
    def add_pre3x8(self,num):
        """ Add 3x8 numbered predecoder """
        if (self.num_inputs == 3):
            offset = vector(self.routing_width,0)
            mirror ="R0"
        else:
            height = self.no_of_pre2x4*self.pre2_4.height + num*self.pre3_8.height
            offset = vector(self.routing_width+self.pre3_8.width, height)
            mirror="MY"

        # If we had 2x4 predecodes, those are used as the lower
        # decode output bits
        in_index_offset = num * 3 + self.no_of_pre2x4 * 2
        out_index_offset = num * 8 + self.no_of_pre2x4 * 4

        pins = []
        for input_index in range(3):
            pins.append("A[{0}]".format(input_index + in_index_offset))
        for output_index in range(8):
            pins.append("out[{0}]".format(output_index + out_index_offset))
        if self.use_flops:
            pins.append("clk")
        pins.extend(["vdd", "gnd"])

        self.pre3x8_inst.append(self.add_inst(name="pre3x8[{0}]".format(num), 
                                              mod=self.pre3_8,
                                              offset=offset,
                                              mirror=mirror))
        self.connect_inst(pins)

        # The 3x8 predecoders will be stacked, so use yoffset
        self.add_pre3x8_pins(num,offset)

    def add_pre3x8_pins(self,num,offset):
        """ Add the input pins to the 3x8 predecoder at the given offset """

        for i in range(3):            
            pin = self.pre3x8_inst[num].get_pin(self.predec_in.format(i))
            pin_offset = pin.ll()
            self.add_layout_pin(text="A[{0}]".format(i + 3*num + 2*self.no_of_pre2x4),
                                layer="metal2", 
                                offset=pin_offset,
                                width=pin.width(),
                                height=pin.height())



    def create_row_decoder(self):
        """ Create the row-decoder by placing NAND2/NAND3 and Inverters
        and add the primary decoder output pins. """
        if (self.num_inputs >= 4):
            self.add_decoder_nand_array()
            self.add_decoder_inv_array()
            self.route_decoder()
            self.add_body_contacts()

    def add_decoder_nand_array(self):
        """ Add a column of NAND gates for final decode """
        
        # Row Decoder NAND GATE array for address inputs <5.
        if len(self.predec_groups) == 2:
            self.add_nand_array(nand_mod=self.nand2)
            # FIXME: Can we convert this to the connect_inst with checks?
            for j in range(len(self.predec_groups[1])):
                for i in range(len(self.predec_groups[0])):
                    pins =["out[{0}]".format(i),
                           "out[{0}]".format(j + len(self.predec_groups[0])),
                           "Z[{0}]".format(len(self.predec_groups[0])*j + i),
                           "vdd", "gnd"]
                    self.connect_inst(args=pins, check=False)

        # Row Decoder NAND GATE array for address inputs >5.
        else:
            self.add_nand_array(nand_mod=self.nand3,
                                correct=drc["minwidth_metal1"])
            # This will not check that the inst connections match.
            for k in range(len(self.predec_groups[2])):
                for j in range(len(self.predec_groups[1])):
                    for i in range(len(self.predec_groups[0])):
                        row = len(self.predec_groups[1])*len(self.predec_groups[0]) * k \
                                  + len(self.predec_groups[0])*j + i
                        pins = ["out[{0}]".format(i),
                                "out[{0}]".format(j + len(self.predec_groups[0])),
                                "out[{0}]".format(k + len(self.predec_groups[0]) + len(self.predec_groups[1])),
                                "Z[{0}]".format(row),
                                "vdd", "gnd"]
                        self.connect_inst(args=pins, check=False)

    def add_nand_array(self, nand_mod, correct=0):
        """ Add a column of NAND gates for the decoder above the predecoders."""
        
        self.nand_inst = []
        for row in range(self.rows):
            name = "DEC_NAND[{0}]".format(row)
            if ((row % 2) == 1):
                y_off = self.predecoder_height + nand_mod.height*row
                y_dir = 1
                mirror = "R0"
            else:
                y_off = self.predecoder_height + nand_mod.height*(row + 1)
                y_dir = -1
                mirror = "MX"

            self.nand_inst.append(self.add_inst(name=name,
                                                mod=nand_mod,
                                                offset=[self.routing_width, y_off],
                                                mirror=mirror))

            

    def add_decoder_inv_array(self):
        """Add a column of INV gates for the decoder above the predecoders
        and to the right of the NAND decoders."""
        
        z_pin = self.inv.get_pin("Z")
        
        if (self.num_inputs == 4 or self.num_inputs == 5):
            x_off = self.routing_width + self.nand2.width
        else:
            x_off = self.routing_width + self.nand3.width

        self.inv_inst = []
        for row in range(self.rows):
            name = "DEC_INV_[{0}]".format(row)
            if (row % 2 == 1):
                inv_row_height = self.inv.height * row
                mirror = "R0"
                y_dir = 1
            else:
                inv_row_height = self.inv.height * (row + 1)
                mirror = "MX"
                y_dir = -1
            y_off = self.predecoder_height + inv_row_height
            offset = vector(x_off,y_off)
            
            self.inv_inst.append(self.add_inst(name=name,
                                               mod=self.inv,
                                               offset=offset,
                                               mirror=mirror))

            # This will not check that the inst connections match.
            self.connect_inst(args=["Z[{0}]".format(row),
                                    "decode[{0}]".format(row),
                                    "vdd", "gnd"],
                              check=False)


    def route_decoder(self):
        """ Route the nand to inverter in the decoder and add the pins. """
        if OPTS.use_body_taps:
            implant_left = self.nand_inst[0].lx()
            if len(self.pre3x8_inst) > 0:
                predec_module = self.pre3_8
            else:
                predec_module = self.pre2_4
            # add extra implant width for cases when this implant overlaps with wordline driver implant
            # adding even one nand width for safety
            pre_module_width = predec_module.inv_inst[0].width + predec_module.nand_inst[0].width

            row_decoder_nand = self.nand_inst[0].mod
            nand_implant = max(row_decoder_nand.get_layer_shapes("pimplant"), key=lambda x: x.uy())
            implant_extension = nand_implant.uy() - row_decoder_nand.height

            implant_height = drc["minwidth_implant"]
            y_offset = self.nand_inst[0].by() - implant_extension - implant_height

            row_decoder_width = self.nand_inst[0].width + self.inv_inst[0].width

            implant_width = (max(row_decoder_width, pre_module_width) + self.implant_width + self.implant_space +
                             0.5*row_decoder_nand.width)

            self.add_rect("pimplant", offset=vector(implant_left, y_offset), height=implant_height,
                          width=implant_width)
            # add nwell to cover the implant
            x_offset = implant_left + max(row_decoder_width, pre_module_width)
            nwell_height = self.well_width + self.well_enclose_implant
            nwell_width = self.well_width + self.well_enclose_implant + 0.5*row_decoder_nand.width
            y_offset = self.nand_inst[0].by() - nwell_height
            self.add_rect("nwell", offset=vector(x_offset, y_offset),
                          width=nwell_width, height=nwell_height)

        for row in range(self.rows):

            # route nand output to output inv input
            zr_pos = self.nand_inst[row].get_pin("Z").rc()
            al_pos = self.inv_inst[row].get_pin("A").lc()
            # ensure the bend is in the middle 
            mid1_pos = vector(0.5*(zr_pos.x+al_pos.x), zr_pos.y)
            mid2_pos = vector(0.5*(zr_pos.x+al_pos.x), al_pos.y)
            self.add_path("metal1", [zr_pos, mid1_pos, mid2_pos, al_pos])
            
            z_pin = self.inv_inst[row].get_pin("Z")
            self.add_layout_pin(text="decode[{0}]".format(row),
                                layer="metal1",
                                offset=z_pin.ll(),
                                width=z_pin.width(),
                                height=z_pin.height())

    def add_body_contacts(self):
        """Add contacts to the left of the nand gates"""
        active_height = contact.active.first_layer_width
        active_width = utils.ceil(drc["minarea_cont_active_thin"] / active_height)
        implant_height = drc["minwidth_implant"]
        implant_enclosure = drc["ptx_implant_enclosure_active"]
        implant_width = max(utils.ceil(active_width + 2*implant_enclosure),
                            utils.ceil(drc["minarea_implant"]/implant_height))
        implant_x = self.nand_inst[0].lx() - 0.5*implant_width
        num_contacts = self.calculate_num_contacts(active_width)

        nwell_width = implant_width + 2*self.well_enclose_implant
        nwell_height = implant_height + 2*self.well_enclose_implant

        for row in range(self.rows):
            gnd_pin = self.nand_inst[row].get_pin("gnd")
            self.add_contact_center(contact.contact.active_layers,
                                    offset=vector(implant_x, gnd_pin.cy()), size=[num_contacts, 1])
            self.add_rect_center("pimplant", offset=vector(implant_x, gnd_pin.cy()),
                                 width=implant_width, height=implant_height)

            vdd_pin = self.nand_inst[row].get_pin("vdd")
            self.add_contact_center(contact.contact.active_layers,
                                    offset=vector(implant_x, vdd_pin.cy()), size=[num_contacts, 1])
            self.add_rect_center("nimplant", offset=vector(implant_x, vdd_pin.cy()),
                                 width=implant_width, height=implant_height)
            self.add_rect_center("nwell", offset=(implant_x, vdd_pin.cy()),
                                width=nwell_width, height=nwell_height)

    def create_vertical_rail(self):
        """ Creates vertical metal 2 rails to connect predecoder and decoder stages."""

        # This is not needed for inputs <4 since they have no pre/decode stages.
        if (self.num_inputs >= 4):
            # Array for saving the X offsets of the vertical rails. These rail
            # offsets are accessed with indices.
            self.rail_x_offsets = []
            for i in range(self.total_number_of_predecoder_outputs):
                # The offsets go into the negative x direction
                # assuming the predecodes are placed at (self.routing_width,0)
                x_offset = self.metal2_pitch * i
                self.rail_x_offsets.append(x_offset+0.5*self.m2_width)
                self.add_rect(layer="metal2",
                              offset=vector(x_offset,0),
                              width=drc["minwidth_metal2"],
                              height=self.height)

            self.connect_rails_to_predecodes()
            self.connect_rails_to_decoder()

    def connect_rails_to_predecodes(self):
        """ Iterates through all of the predecodes and connects to the rails including the offsets """

        for pre_num in range(self.no_of_pre2x4):
            for i in range(4):
                index = pre_num * 4 + i
                out_name = "out[{}]".format(i)
                pin = self.pre2x4_inst[pre_num].get_pin(out_name)
                self.connect_rail(index, pin) 

        for pre_num in range(self.no_of_pre3x8):
            for i in range(8):
                index = pre_num * 8 + i + self.no_of_pre2x4 * 4
                out_name = "out[{}]".format(i)
                pin = self.pre3x8_inst[pre_num].get_pin(out_name)
                self.connect_rail(index, pin) 

    def connect_rails_to_decoder(self):
        """ Use the self.predec_groups to determine the connections to the decoder NAND gates.
        Inputs of NAND2/NAND3 gates come from different groups.
        For example for these groups [ [0,1,2,3] ,[4,5,6,7],
        [8,9,10,11,12,13,14,15] ] the first NAND3 inputs are connected to
        [0,4,8] and second NAND3 is connected to [1,4,8]  ........... and the
        128th NAND3 is connected to [3,7,15]
        """
        row_index = 0
        if len(self.predec_groups) == 2:
            for index_B in self.predec_groups[1]:
                for index_A in self.predec_groups[0]:
                    self.connect_rail_m2(index_A, self.nand_inst[row_index].get_pin("A"))
                    self.connect_rail_m2(index_B, self.nand_inst[row_index].get_pin("B"))
                    row_index = row_index + 1

        else:
            for index_C in self.predec_groups[2]:
                for index_B in self.predec_groups[1]:
                    for index_A in self.predec_groups[0]:
                        self.connect_rail_m2(index_A, self.nand_inst[row_index].get_pin("A"))
                        self.connect_rail_m2(index_B, self.nand_inst[row_index].get_pin("B"))
                        self.connect_rail_m2(index_C, self.nand_inst[row_index].get_pin("C"))
                        row_index = row_index + 1

    def connect_rail_m2(self, rail_index, pin):

        if pin.name == "A":  # connect directly with M1
            rail_offset = vector(self.rail_x_offsets[rail_index], pin.cy())
            self.add_path("metal1", [rail_offset, pin.center()])
            self.add_via_center(layers=contact.m1m2.layer_stack, offset=rail_offset, rotate=0)
        else:
            max_rail = max(self.rail_x_offsets)
            via_x = max_rail + 2 * self.m1_space + 0.5 * contact.m1m2.first_layer_height
            if pin.name == "B":
                rail_offset = vector(self.rail_x_offsets[rail_index], pin.cy())
                self.add_via_center(layers=contact.m2m3.layer_stack, offset=rail_offset, rotate=0)
                via_offset = vector(via_x, pin.cy())
                self.add_path("metal3", [rail_offset, via_offset])
                # add metal3 fill , fill up since C pin will be below if applicable
                min_height = self.metal1_minwidth_fill
                fill_height = max(0, min_height - via_offset.x - rail_offset.x)
                self.add_rect("metal3", offset=vector(rail_offset.x - 0.5*self.m3_width,
                                                      pin.cy() + 0.5*contact.m2m3.second_layer_height),
                              height=fill_height)

                self.add_via_center(layers=contact.m2m3.layer_stack, offset=via_offset, rotate=90)
                self.add_path("metal2", [via_offset, pin.center()])
                self.add_via_center(layers=contact.m1m2.layer_stack, offset=pin.center(), rotate=0)
            else:
                rail_y = pin.cy() - 0.5*contact.m2m3.second_layer_height - self.line_end_space - 0.5*self.m3_width
                rail_offset = vector(self.rail_x_offsets[rail_index], rail_y)
                self.add_via_center(layers=contact.m2m3.layer_stack, offset=rail_offset, rotate=0)
                self.add_path("metal3", [rail_offset, vector(pin.rx(), rail_y)])
                self.add_path("metal3", [vector(pin.cx(), rail_y), pin.center()])
                self.add_via_center(layers=contact.m1m2.layer_stack, offset=pin.center(), rotate=0)
                self.add_via_center(layers=contact.m2m3.layer_stack, offset=pin.center(), rotate=0)
                fill_height = contact.m2m3.second_layer_height
                fill_width = utils.ceil(drc["minarea_metal1_minwidth"]/fill_height)
                offset = vector(pin.lx() - 0.5*self.m2_width, pin.cy() - 0.5*fill_height)
                self.add_rect("metal2", offset=offset, width=fill_width, height=fill_height)

    def copy_power_pin(self, pin):
        if hasattr(OPTS, 'separate_vdd') and pin.name == 'vdd':
            width = pin.rx()
        else:
            width = self.width
        self.add_layout_pin(text=pin.name,
                            layer=pin.layer,
                            offset=vector(0, pin.by()),
                            width=width,
                            height=pin.height())

    def route_vdd_gnd(self):
        """ Add a pin for each row of vdd/gnd which are must-connects next level up. """
        for i in list(range(0, len(self.nand_inst), 2)) + [-1]:
            inst = self.nand_inst[i]
            self.copy_power_pin(inst.get_pin("vdd"))
            self.copy_power_pin(inst.get_pin("gnd"))
        for predecoder in self.pre2x4_inst + self.pre3x8_inst:
            for pin in predecoder.get_pins("vdd") + predecoder.get_pins("gnd"):
                self.copy_power_pin(pin)

        

    def connect_rail(self, rail_index, pin):
        """ Connect the routing rail to the given metal1 pin  """
        rail_pos = vector(self.rail_x_offsets[rail_index],pin.lc().y)
        self.add_path("metal1", [rail_pos, pin.lc()])
        self.add_via_center(layers=("metal1", "via1", "metal2"),
                            offset=rail_pos,
                            rotate=0)

        
    def analytical_delay(self, slew, load = 0.0):
        # A -> out
        if self.determine_predecodes(self.num_inputs)[1]==0:
            pre = self.pre2_4
            nand = self.nand2
        else:
            pre = self.pre3_8
            nand = self.nand3
        a_t_out_delay = pre.analytical_delay(slew=slew,load = nand.input_load())

        # out -> z
        out_t_z_delay = nand.analytical_delay(slew= a_t_out_delay.slew,
                                  load = self.inv.input_load())
        result = a_t_out_delay + out_t_z_delay

        # Z -> decode_out
        z_t_decodeout_delay = self.inv.analytical_delay(slew = out_t_z_delay.slew , load = load)
        result = result + z_t_decodeout_delay
        return result

        
    def input_load(self):
        if self.determine_predecodes(self.num_inputs)[1]==0:
            pre = self.pre2_4
        else:
            pre = self.pre3_8
        return pre.input_load()
