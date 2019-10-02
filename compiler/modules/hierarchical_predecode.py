import math
from importlib import reload

import debug
from base import contact
from base import design
from base.vector import vector
from globals import OPTS
from pgates.pgate import pgate
from pgates.pinv import pinv
from pgates.pnand2 import pnand2
from pgates.pnand3 import pnand3


class hierarchical_predecode(design.design):
    """
    Pre 2x4 and 3x8 decoder shared code.
    """
    def __init__(self, input_number, route_top_rail=True, use_flops=False):
        self.number_of_inputs = input_number
        self.number_of_outputs = int(math.pow(2, self.number_of_inputs))
        name = "pre{0}x{1}".format(self.number_of_inputs,self.number_of_outputs)
        if not route_top_rail:
            name += "_no_top"
        if use_flops:
            name += "_flops"
        design.design.__init__(self, name=name)
        self.route_top_rail = route_top_rail
        self.use_flops = use_flops

        c = __import__(OPTS.bitcell)
        self.mod_bitcell = getattr(c, OPTS.bitcell)
        self.bitcell_height = self.mod_bitcell.height

        if self.use_flops:
            if hasattr(OPTS, "predecoder_flop"):
                predecoder_flop = OPTS.predecoder_flop
            else:
                predecoder_flop = "ms_flop_horz_pitch"
            c = reload(__import__(predecoder_flop))
            self.mod_ms_flop = getattr(c, predecoder_flop)
            self.flop = self.mod_ms_flop()
            self.add_mod(self.flop)
            self.module_height = self.flop.height
        else:
            self.module_height = pgate.get_default_height()

    
    def add_pins(self):
        in_name = "flop_in[{}]" if self.use_flops else "in[{}]"
        for k in range(self.number_of_inputs):
            self.add_pin(in_name.format(k))
        for i in range(self.number_of_outputs):
            self.add_pin("out[{0}]".format(i))
        if self.use_flops:
            self.add_pin("clk")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_modules(self):
        """ Create the INV and NAND gate """

        inverter_size = OPTS.predecode_sizes[1]

        self.inv = pinv(size=inverter_size, height=self.module_height)
        self.add_mod(self.inv)
        self.nand = self.create_nand(self.number_of_inputs)
        self.add_mod(self.nand)

        # TODO use buffer stages in place of single output inverter

        if not self.route_top_rail:
            self.top_inv = pinv(size=inverter_size, contact_nwell=False, height=self.module_height)
            self.add_mod(self.top_inv)
            self.top_nand = self.create_nand(self.number_of_inputs, contact_nwell=False)
            self.add_mod(self.top_nand)
        else:
            self.top_inv = self.inv
            self.top_nand = self.nand

    def create_nand(self, inputs, contact_nwell=True):
        """ Create the NAND for the predecode input stage """
        nand_size = OPTS.predecode_sizes[0]
        if inputs == 2:
            nand = pnand2(size=nand_size, contact_nwell=contact_nwell, height=self.module_height)
        elif inputs == 3:
            nand = pnand3(size=nand_size, contact_nwell=contact_nwell, height=self.module_height)
        else:
            return debug.error("Invalid number of predecode inputs.",-1)
        return nand

    def setup_flop_offsets(self):
        x_offset = 0
        self.clk_x_offset = x_offset + 0.5*self.m2_width
        self.rails["clk"] = self.clk_x_offset
        x_offset += self.m2_pitch + 0.5 * self.m2_width
        for rail_index in range(self.number_of_inputs):
            self.rails["flop_in[{}]".format(rail_index)] = x_offset
            x_offset += self.m2_pitch
        module_space = (self.line_end_space - self.m2_space)
        self.flop_x_offset = x_offset + module_space
        self.mid_rail_x = self.flop_x_offset + self.flop.width + self.m2_pitch


    def setup_input_inv_offsets(self):
        # Non inverted input rails
        for rail_index in range(self.number_of_inputs):
            xoffset = rail_index * self.m2_pitch + 0.5 * self.m2_width
            self.rails["in[{}]".format(rail_index)] = xoffset
        # x offset for input inverters
        left_s_d = self.inv.get_left_source_drain()
        self.x_off_inv_1 = self.number_of_inputs * self.m2_pitch - left_s_d
        self.mid_rail_x = self.x_off_inv_1 + self.inv.width

    def setup_constraints(self):
        # we are going to use horizontal vias, so use the via height
        # use a conservative douple spacing just to get rid of annoying via DRCs
        self.m2_pitch = contact.m1m2.width + self.parallel_line_space
        
        # The rail offsets are indexed by the label
        self.rails = {}

        if self.use_flops:
            self.setup_flop_offsets()
        else:
            self.setup_input_inv_offsets()


        
        # Creating the right hand side metal2 rails for output connections
        for rail_index in range(2 * self.number_of_inputs):
            xoffset = self.mid_rail_x + ((rail_index+1) * self.m2_pitch) + 0.5*self.m2_width
            if rail_index < self.number_of_inputs:
                self.rails["Abar[{}]".format(rail_index)]=xoffset
            else:
                self.rails["A[{}]".format(rail_index-self.number_of_inputs)]=xoffset

        # x offset to NAND decoder includes the left rails, mid rails and inverters, plus an extra m2 pitch
        self.x_off_nand = self.mid_rail_x + (1 + 2*self.number_of_inputs) * self.m2_pitch

                       
        # x offset to output inverters
        self.x_off_inv_2 = self.x_off_nand + self.nand.width

        # Height width are computed 
        self.width = self.x_off_inv_2 + self.inv.width
        self.height = self.number_of_outputs * self.nand.height

    def create_rails(self):
        """ Create all of the rails for the inputs and vdd/gnd/inputs_bar/inputs """
        # extend rail to highest pin
        highest_pin = "C" if self.number_of_inputs == 3 else "B"
        top_space = self.nand.height - self.nand.get_pin(highest_pin).uy()
        for label in self.rails.keys():
            # these are not primary inputs, so they shouldn't have a
            # label or LVS complains about different names on one net
            if label.startswith("in") or label.startswith("flop_in") or label == "clk":
                self.add_layout_pin(text=label,
                                    layer="metal2",
                                    offset=vector(self.rails[label] - 0.5*self.m2_width, 0), 
                                    width=self.m2_width,
                                    height=self.height - 2*self.m2_space)
            else:
                self.add_rect(layer="metal2",
                              offset=vector(self.rails[label] - 0.5*self.m2_width, 0), 
                              width=self.m2_width,
                              height=self.height - top_space)

    def add_input_inverters(self):
        """ Create the input inverters to invert input signals for the decode stage. """

        self.in_inst = []
        for row in range(self.number_of_inputs):
            if not self.use_flops:
                name = "Xpre_inv[{0}]".format(row)
                if (row % 2 == 1):
                    y_off = row * (self.inv.height)
                    mirror = "R0"
                else:
                    y_off = (row + 1) * (self.inv.height)
                    mirror="MX"
                offset = vector(self.x_off_inv_1, y_off)
                self.in_inst.append(self.add_inst(name=name,
                                                  mod=self.inv,
                                                  offset=offset,
                                                  mirror=mirror))
                self.connect_inst(["in[{0}]".format(row),
                                   "inbar[{0}]".format(row),
                                   "vdd", "gnd"])
            else:
                name = "Xflop[{0}]".format(row)
                if (row % 2 == 1):
                    y_off = row * (self.flop.height)
                    mirror = "R0"
                else:
                    y_off = (row + 1) * (self.flop.height)
                    mirror="MX"
                offset = vector(self.flop_x_offset, y_off)
                self.in_inst.append(self.add_inst(name=name,
                                                  mod=self.flop,
                                                  offset=offset,
                                                  mirror=mirror))
                self.connect_inst(["flop_in[{0}]".format(row),
                                   "in[{0}]".format(row),
                                   "inbar[{0}]".format(row),
                                   "clk", "vdd", "gnd"])


            
    def add_output_inverters(self):
        """ Create inverters for the inverted output decode signals. """
        
        self.inv_inst = []
        for inv_num in range(self.number_of_outputs):
            name = "Xpre_nand_inv[{}]".format(inv_num)
            if (inv_num % 2 == 1):
                y_off = inv_num * self.inv.height
                mirror = "R0"
            else:
                y_off =(inv_num + 1)*self.inv.height
                mirror = "MX"
            offset = vector(self.x_off_inv_2, y_off)
            if inv_num < self.number_of_outputs - 1:
                inv = self.inv
            else:
                inv = self.top_inv
            self.inv_inst.append(self.add_inst(name=name,
                                               mod=inv,
                                               offset=offset,
                                               mirror=mirror))
            self.connect_inst(["Z[{}]".format(inv_num),
                               "out[{}]".format(inv_num),
                               "vdd", "gnd"])
            
            

    def add_nand(self,connections):
        """ Create the NAND stage for the decodes """
        self.nand_inst = []        
        for nand_input in range(self.number_of_outputs):
            inout = str(self.number_of_inputs)+"x"+str(self.number_of_outputs)
            name = "Xpre{0}_nand[{1}]".format(inout,nand_input)
            if (nand_input % 2 == 1):
                y_off = nand_input * self.inv.height
                mirror = "R0"
            else:
                y_off = (nand_input + 1) * self.inv.height
                mirror = "MX"
            offset = vector(self.x_off_nand, y_off)
            if nand_input < self.number_of_outputs - 1:
                nand = self.nand
            else:
                nand = self.top_nand
            self.nand_inst.append(self.add_inst(name=name,
                                                mod=nand,
                                                offset=offset,
                                                mirror=mirror))
            self.connect_inst(connections[nand_input])
            

    def route(self):
        if self.use_flops:
            self.route_input_flops()
        else:
            self.route_input_inverters()
            self.route_inputs_to_rails()
        self.route_nand_to_rails()
        self.route_output_inverters()        
        self.route_vdd_gnd()

    def route_inputs_to_rails(self):
        """ Route the uninverted inputs to the second set of rails """
        for num in range(self.number_of_inputs):
            # route one signal next to each vdd/gnd rail since this is
            # typically where the p/n devices are and there are no
            # pins in the nand gates. 
            y_offset = (num+self.number_of_inputs) *self.inv.height + 0.5*self.rail_height +\
                       contact.m1m2.height + self.m1_space
            in_pin = "in[{}]".format(num)            
            a_pin = "A[{}]".format(num)
            in_pos = vector(self.rails[in_pin],y_offset)
            a_pos = vector(self.rails[a_pin],y_offset)            
            self.add_path("metal1",[in_pos, a_pos])
            self.add_via_center(layers = ("metal1", "via1", "metal2"),
                                offset=[self.rails[in_pin], y_offset],
                                rotate=0)
            self.add_via_center(layers = ("metal1", "via1", "metal2"),
                                offset=[self.rails[a_pin], y_offset],
                                rotate=0)

    def route_output_inverters(self):
        """
        Route all conections of the outputs inverters 
        """
        for num in range(self.number_of_outputs):

            # route nand output to output inv input
            z_pin = self.nand_inst[num].get_pin("Z")
            a_pin = self.inv_inst[num].get_pin("A")
            self.add_rect("metal1", offset=vector(z_pin.rx(), a_pin.by()), width=a_pin.lx()-z_pin.rx())

            self.copy_layout_pin(self.inv_inst[num], "Z", "out[{}]".format(num))

    def route_input_flops(self):
        """
        Route flip flop inputs and outputs
        """
        for row in range(self.number_of_inputs):
            # connect din
            din_pin = self.in_inst[row].get_pin("din")
            rail_x = self.rails["flop_in[{}]".format(row)]
            self.add_contact_center(contact.m2m3.layer_stack, offset=vector(rail_x, din_pin.cy()))
            self.add_rect("metal3", offset=vector(rail_x, din_pin.by()), width=din_pin.lx() - rail_x)
            self.add_contact(contact.m2m3.layer_stack, offset=din_pin.ll(), rotate=90)

            # connect clk
            clk_pin = self.in_inst[row].get_pin("clk")
            rail_x = self.rails["clk"]
            self.add_contact_center(contact.m1m2.layer_stack, offset=vector(rail_x, clk_pin.cy()))
            self.add_rect("metal1", offset=vector(rail_x, clk_pin.by()), width=clk_pin.lx() - rail_x)

            m3_min_width = self.metal1_minwidth_fill

            # route dout
            flop_out = self.in_inst[row].get_pin("dout")
            out_pin = "A[{}]".format(row)
            rail_x = self.rails[out_pin]
            self.add_rect("metal3", offset=vector(flop_out.cx(), flop_out.cy() - 0.5*self.m3_width),
                          width=max(rail_x - flop_out.cx(), m3_min_width))
            self.add_contact_center(contact.m2m3.layer_stack, offset=vector(rail_x, flop_out.cy()))

            # route dout_bar
            rail_x = self.rails["Abar[{}]".format(row)]
            flop_out_bar = self.in_inst[row].get_pin("dout_bar")
            self.add_contact(contact.m2m3.layer_stack,
                             offset=flop_out_bar.lr() + vector(contact.m2m3.second_layer_height, 0),
                             rotate=90)
            self.add_rect("metal3", offset=flop_out_bar.lr(), width=max(rail_x - flop_out_bar.rx(), m3_min_width))
            self.add_contact_center(contact.m2m3.layer_stack, offset=vector(rail_x, flop_out_bar.cy()))


    
    def route_input_inverters(self):
        """
        Route all conections of the inputs inverters [Inputs, outputs, vdd, gnd] 
        """
        a_rails = [self.rails[key] for key in self.rails if key.startswith("A")]
        left_rails = min(a_rails) - 3*self.m1_space
        for inv_num in range(self.number_of_inputs):
            out_pin = "Abar[{}]".format(inv_num)
            in_pin = "in[{}]".format(inv_num)
            
            #add output so that it is just below the vdd or gnd rail
            # since this is where the p/n devices are and there are no
            # pins in the nand gates.
            y_offset = (inv_num+1) * self.inv.height - 0.5*self.rail_height - 2*self.m1_space -\
                       0.5*contact.m1m2.first_layer_height
            inv_out_pos = self.in_inst[inv_num].get_pin("Z").rc()
            rail_pos = vector(self.rails[out_pin],y_offset)
            self.add_path("metal1", [inv_out_pos, vector(left_rails, inv_out_pos.y),
                                     vector(left_rails, y_offset), rail_pos])
            self.add_via_center(layers = ("metal1", "via1", "metal2"),
                                offset=rail_pos,
                                rotate=0)

            
            #route input
            inv_in_pos = self.in_inst[inv_num].get_pin("A").lc()
            in_pos = vector(self.rails[in_pin],inv_in_pos.y)
            self.add_path("metal1", [in_pos, inv_in_pos])
            self.add_via_center(layers=("metal1", "via1", "metal2"),
                                offset=in_pos,
                                rotate=0)
            

    def route_nand_to_rails(self):
        # This 2D array defines the connection mapping 
        nand_input_line_combination = self.get_nand_input_line_combination()
        for k in range(self.number_of_outputs):
            # create x offset list         
            index_lst= nand_input_line_combination[k]

            if self.number_of_inputs == 2:
                gate_lst = ["A","B"]
            else:
                gate_lst = ["A","B","C"]

            # this will connect pins A,B or A,B,C
            max_rail = max(self.rails.values())
            layers = ("metal1", "via1", "metal2")
            via_x = max_rail + 2*self.m1_space + 0.5*contact.m1m2.first_layer_height
            for rail_pin, gate_pin_name in zip(index_lst,gate_lst):
                gate_pin = self.nand_inst[k].get_pin(gate_pin_name)
                pin_pos = gate_pin.lc()
                rail_pos = vector(self.rails[rail_pin], pin_pos.y)
                self.add_via_center(layers=layers, offset=rail_pos, rotate=0)
                self.add_path("metal1", [rail_pos, vector(via_x, rail_pos.y)])
                via_offset = vector(via_x, rail_pos.y)
                self.add_via_center(layers=layers, offset=via_offset, rotate=90)
                self.add_path("metal2", [via_offset, pin_pos])
                if gate_pin_name == "A":
                    y_offset = gate_pin.cy()
                else:
                    if k % 2 == 0:
                        y_offset = gate_pin.cy() + 0.5*(contact.m1m2.second_layer_height - self.m1_width)
                    else:
                        y_offset = gate_pin.cy() - 0.5*(contact.m1m2.second_layer_height - self.m1_width)
                self.add_via_center(layers=layers, offset=vector(gate_pin.cx(), y_offset), rotate=0)

    def route_vdd_gnd(self):
        """ Add a pin for each row of vdd/gnd which are must-connects next level up. """

        for num in range(0,self.number_of_outputs):
            # this will result in duplicate polygons for rails, but who cares
            
            # use the inverter offset even though it will be the nand's too
            (gate_offset, y_dir) = self.get_gate_offset(0, self.inv.height, num)

            # route vdd
            vdd_pin = self.nand_inst[num].get_pin("vdd")
            if hasattr(OPTS, 'separate_vdd') and OPTS.separate_vdd and num > len(self.in_inst):
                x_start = vdd_pin.lx()
            else:
                x_start = 0
            self.add_layout_pin(text="vdd",
                                height=self.rail_height,
                                layer="metal1",
                                offset=vector(x_start, vdd_pin.by()),
                                width=self.inv_inst[num].rx()-x_start)

            # route gnd
            gnd_offset = self.nand_inst[num].get_pin("gnd").ll().scale(0,1)
            self.add_layout_pin(text="gnd",
                                layer="metal1",
                                height=self.rail_height,
                                offset=gnd_offset,
                                width=self.inv_inst[num].rx())
        


