import contact
import pgate
import debug
from tech import drc, parameter, spice
from ptx import ptx
from vector import vector
from globals import OPTS
import utils

class pnand3(pgate.pgate):
    """
    This module generates gds of a parametrically sized 3-input nand.
    This model use ptx to generate a 3-input nand within a certain height.
    """

    c = reload(__import__(OPTS.bitcell))
    bitcell = getattr(c, OPTS.bitcell)

    unique_id = 1
    
    def __init__(self, size=1, height=bitcell.height):
        """ Creates a cell for a simple 3 input nand """
        name = "pnand3_{0}".format(pnand3.unique_id)
        pnand3.unique_id += 1
        pgate.pgate.__init__(self, name)
        debug.info(2, "create pnand3 structure {0} with size of {1}".format(name, size))

        self.nmos_size = 3*size
        self.pmos_size = parameter["beta"]*size
        self.nmos_width = self.nmos_size*drc["minwidth_tx"]
        self.pmos_width = self.pmos_size*drc["minwidth_tx"]
        self.height = height

        self.add_pins()
        self.create_layout()
        #self.DRC_LVS()

        
    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "B", "C", "Z", "vdd", "gnd"])

    def create_layout(self):
        """ Calls all functions related to the generation of the layout """
        self.determine_tx_mults()
        # FIXME: Allow multiple fingers
        debug.check(self.tx_mults==1,"Only Single finger pnand3 is supported now.")
        self.create_ptx()
        self.setup_layout_constants()
        self.add_supply_rails()
        self.add_ptx()
        self.connect_rails()
        self.add_well_contacts()
        self.extend_wells(self.well_pos)
        self.route_inputs()
        self.route_output()

    def determine_tx_mults(self):

        if "metal1_to_metal1_wide" in drc:
            self.wide_m1_space = drc["metal1_to_metal1_wide"]
        else:
            self.wide_m1_space = drc["metal1_to_metal1"]

        # metal spacing to allow contacts on any layer
        self.max_input_width = max(contact.m1m2.first_layer_width,
                                 contact.m2m3.first_layer_width, contact.m2m3.second_layer_width)
        self.input_spacing = self.max_input_width + self.wide_m1_space
        # pmos gate contact to A input to B input
        self.min_channel = 4*self.input_spacing
        pgate.pgate.determine_tx_mults(self)

    def create_ptx(self):
        """ Create the PMOS and NMOS transistors. """
        self.nmos = ptx(width=self.nmos_width,
                        mults=self.tx_mults,
                        tx_type="nmos",
                        dummy_pos=[0, 1],
                        connect_poly=True,
                        connect_active=False)
        self.add_mod(self.nmos)
        self.nmos2 = ptx(width=self.nmos_width,
                        mults=self.tx_mults,
                        tx_type="nmos",
                        dummy_pos=[],
                        connect_poly=True,
                        connect_active=False)
        self.add_mod(self.nmos2)
        self.nmos3 = ptx(width=self.nmos_width,
                        mults=self.tx_mults,
                        tx_type="nmos",
                        dummy_pos=[2, 3],
                        connect_poly=True,
                        connect_active=True)
        self.add_mod(self.nmos3)

        self.pmos = ptx(width=self.pmos_width,
                        mults=self.tx_mults,
                        tx_type="pmos",
                        dummy_pos=[0, 1],
                        connect_poly=True,
                        connect_active=True)
        self.add_mod(self.pmos)
        self.pmos2 = ptx(width=self.pmos_width,
                        mults=self.tx_mults,
                        tx_type="pmos",
                        dummy_pos=[],
                        connect_poly=True,
                        connect_active=False)
        self.add_mod(self.pmos2)
        self.pmos3 = ptx(width=self.pmos_width,
                        mults=self.tx_mults,
                        tx_type="pmos",
                        dummy_pos=[2, 3],
                        connect_poly=True,
                        connect_active=True)
        self.add_mod(self.pmos3)
        

    def setup_layout_constants(self):
        """ Pre-compute some handy layout parameters. """
        
        # Compute the other pmos2 location, by determining offset to overlap the
        # source and drain pins
        self.overlap_offset = vector((self.pmos.get_pin("D").ll() - self.pmos.get_pin("S").ll()).x, 0)

        tx_width = 7*self.pmos.poly_pitch + self.pmos.poly_width

        # the well width is determined by the multi-finger PMOS device width plus
        # the well contact width and half well enclosure on both sides
        well_contact = contact.contact(layer_stack=("cont_active", "contact", "cont_metal1"), 
                                implant_type="n",
                                well_type="n")
        # width of active and one side of enclosure of well around active
        active_implant_width = well_contact.first_layer_width + drc["well_enclosure_active"]
        self.well_width = tx_width + drc["poly_dummy_to_active"] +  active_implant_width
        self.width = self.well_width
        # Height is an input parameter, so it is not recomputed.
        
    def add_supply_rails(self):
        """ Add vdd/gnd rails to the top and bottom. """
        self.add_layout_pin_center_rect(text="gnd",
                                        layer="metal1",
                                        offset=vector(0.5*self.width,0),
                                        height = self.rail_height,
                                        width=self.width)

        self.add_layout_pin_center_rect(text="vdd",
                                        layer="metal1",
                                        offset=vector(0.5*self.width,self.height),
                                        height = self.rail_height,
                                        width=self.width)

    def add_ptx(self):
        """ 
        Add PMOS and NMOS to the layout at the upper-most and lowest position
        to provide maximum routing in channel
        """

        # x offset should be first dummy poly to active
        x_offset = 2*self.pmos.poly_pitch - self.pmos.end_to_poly

        active_to_bottom_implant = self.pmos.active_offset.y - self.pmos.implant_offset.y
        active_bottom_to_top_implant = self.pmos.implant_height - active_to_bottom_implant

        pmos1_pos = vector(x_offset, self.height-active_bottom_to_top_implant)

        self.pmos1_inst=self.add_inst(name="pnand3_pmos1",
                                      mod=self.pmos,
                                      offset=pmos1_pos)
        self.connect_inst(["vdd", "A", "Z", "vdd"])

        pmos2_pos = pmos1_pos + self.overlap_offset
        self.pmos2_inst = self.add_inst(name="pnand3_pmos2",
                                        mod=self.pmos2,
                                        offset=pmos2_pos)
        self.connect_inst(["Z", "B", "vdd", "vdd"])

        self.pmos3_pos = pmos2_pos + self.overlap_offset
        self.pmos3_inst = self.add_inst(name="pnand3_pmos3",
                                        mod=self.pmos3,
                                        offset=self.pmos3_pos)
        self.connect_inst(["Z", "C", "vdd", "vdd"])
        
        # place NMOS so that its implant aligns with cell boundary
        nmos_y_offset = self.nmos.active_offset.y - self.nmos.implant_offset.y        
        nmos1_pos = vector(x_offset, nmos_y_offset)

        self.nmos1_inst=self.add_inst(name="pnand3_nmos1",
                                      mod=self.nmos,
                                      offset=nmos1_pos)
        self.connect_inst(["Z", "C", "net1", "gnd"])

        nmos2_pos = nmos1_pos + self.overlap_offset
        self.nmos2_inst=self.add_inst(name="pnand3_nmos2",
                                      mod=self.nmos2,
                                      offset=nmos2_pos)
        self.connect_inst(["net1", "B", "net2", "gnd"])
        

        self.nmos3_pos = nmos2_pos + self.overlap_offset
        self.nmos3_inst=self.add_inst(name="pnand3_nmos3",
                                      mod=self.nmos3,
                                      offset=self.nmos3_pos)
        self.connect_inst(["net2", "A", "gnd", "gnd"])
        
        self.output_pos = vector(0,utils.ceil(0.5*(self.height-self.pmos.height + self.nmos.height)))  
        
        # This will help with the wells 
        self.well_pos = vector(0,utils.round_to_grid(0.5*(self.height-self.pmos.height+self.nmos.height)))
        
    def add_well_contacts(self):
        """ Add n/p well taps to the layout and connect to supplies """

        self.add_nwell_contact(self.pmos, self.pmos3_pos, size=[1, 3])
        self.add_pwell_contact(self.nmos, self.nmos3_pos, size=[1, 3])

        
    def connect_rails(self):
        """ Connect the nmos and pmos to its respective power rails """

        self.connect_pin_to_rail(self.nmos1_inst,"S","gnd")

        self.connect_pin_to_rail(self.pmos1_inst,"S","vdd")        

        self.connect_pin_to_rail(self.pmos2_inst,"D","vdd")

    def route_inputs(self):
        """ Route the A and B inputs """
        inputC_yoffset = self.well_pos.y + 1.5*self.input_spacing
        inputB_yoffset = self.well_pos.y - 0.5*self.input_spacing
        inputA_yoffset = self.well_pos.y - 1.5*self.input_spacing
        
        self.route_input_gate(self.pmos3_inst, self.nmos3_inst, inputC_yoffset, "C", position="center")

        self.route_input_gate(self.pmos2_inst, self.nmos2_inst, inputB_yoffset, "B", position="center")

        self.route_input_gate(self.pmos1_inst, self.nmos1_inst, inputA_yoffset, "A", position="center")

        

    def route_output(self):
        """ Route the Z output """
        # PMOS1 drain 
        pmos1_pin = self.pmos1_inst.get_pin("D")
        # PMOS3 drain 
        pmos3_pin = self.pmos3_inst.get_pin("D")
        # NMOS3 drain
        nmos3_pin = self.nmos3_inst.get_pin("D")    

        output_y_offset = self.well_pos.y + 0.5*self.input_spacing
        mid_offset = vector(nmos3_pin.center().x + drc["nand_output_offset"], output_y_offset)
    
        
        # PMOS3 and NMOS3 are drain aligned
        self.add_path("metal2",[pmos3_pin.bc(), mid_offset, nmos3_pin.uc()])
        
        self.add_path("metal2",[pmos1_pin.bc(), mid_offset, nmos3_pin.uc()]) 

        pin_offset = mid_offset - vector(0, 0.5*contact.m1m2.second_layer_height)

        # add extra metal1 to nmos2 drain to fulfill drc requirement
        fill_height = contact.m1m2.first_layer_height
        fill_width = utils.ceil(drc["minarea_metal1_contact"]/fill_height)
        self.add_rect_center(layer="metal1",
                        offset=pin_offset,
                        height=fill_height,
                        width=fill_width)       

        # This extends the output to the edge of the cell
        self.add_contact_center(layers=("metal1", "via1", "metal2"),
                                offset=pin_offset)
        self.add_layout_pin_center_rect(text="Z",
                                        layer="metal1",
                                        offset=pin_offset,
                                        width=contact.m1m2.first_layer_width,
                                        height=contact.m1m2.first_layer_height)



    def input_load(self):
        return ((self.nmos_size+self.pmos_size)/parameter["min_tx_size"])*spice["min_tx_gate_c"]

    def analytical_delay(self, slew, load=0.0):
        r = spice["min_tx_r"]/(self.nmos_size/parameter["min_tx_size"])
        c_para = spice["min_tx_drain_c"]*(self.nmos_size/parameter["min_tx_size"])#ff
        return self.cal_delay_with_rc(r = r, c =  c_para+load, slew = slew)
        
    def analytical_power(self, proc, vdd, temp, load):
        """Returns dynamic and leakage power. Results in nW"""
        c_eff = self.calculate_effective_capacitance(load)
        freq = spice["default_event_rate"]
        power_dyn = c_eff*vdd*vdd*freq
        power_leak = spice["nand3_leakage"]
        
        total_power = self.return_power(power_dyn, power_leak)
        return total_power
        
    def calculate_effective_capacitance(self, load):
        """Computes effective capacitance. Results in fF"""
        c_load = load
        c_para = spice["min_tx_drain_c"]*(self.nmos_size/parameter["min_tx_size"])#ff
        transistion_prob = spice["nand3_transisition_prob"]
        return transistion_prob*(c_load + c_para) 
