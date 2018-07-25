import contact
import pgate
import pnand2
import debug
from tech import drc, parameter, spice
from ptx import ptx
from vector import vector
from globals import OPTS
import utils

class pnor2(pnand2.pnand2):
    """
    This module generates gds of a parametrically sized 2-input nor.
    This model use ptx to generate a 2-input nor within a cetrain height.
    """

    c = reload(__import__(OPTS.bitcell))
    bitcell = getattr(c, OPTS.bitcell)

    unique_id = 1
    
    def __init__(self, size=1, height=bitcell.height):
        """ Creates a cell for a simple 2 input nor """
        name = "pnor2_{0}".format(pnor2.unique_id)
        pnor2.unique_id += 1
        pgate.pgate.__init__(self, name)
        debug.info(2, "create pnor2 structure {0} with size of {1}".format(name, size))

        self.nmos_size = size
        self.pmos_size = 2*parameter["beta"]*size
        self.nmos_width = self.nmos_size*drc["minwidth_tx"]
        self.pmos_width = self.pmos_size*drc["minwidth_tx"]
        self.height = height

        self.add_pins()
        self.create_layout()
        #self.DRC_LVS()

    def create_ptx(self):
        """ Create the PMOS and NMOS transistors. """
        self.nmos = ptx(width=self.nmos_width,
                        mults=self.tx_mults,
                        tx_type="nmos",
                        dummy_pos=[0, 1],
                        connect_poly=True,
                        connect_active=True)
        self.add_mod(self.nmos)
        self.nmos2 = ptx(width=self.nmos_width,
                        mults=self.tx_mults,
                        tx_type="nmos",
                        dummy_pos=[2, 3],
                        connect_poly=True,
                        connect_active=False)
        self.add_mod(self.nmos2)

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
                        dummy_pos=[2, 3],
                        connect_poly=True,
                        connect_active=False)
        self.add_mod(self.pmos2)

    def add_ptx(self):
        """ 
        Add PMOS and NMOS to the layout at the upper-most and lowest position
        to provide maximum routing in channel
        """
        x_offset = 0.5*(self.pmos.width-self.pmos.active_width)

        #place PMOS so that its implant aligns with cell boundary
        # account for active_offset translation that happens after creation

        pmos_bottom = self.height - (self.pmos.implant_rect.offset.y + self.pmos.implant_rect.height)

        pmos1_pos = vector(x_offset, pmos_bottom)

        self.pmos1_inst=self.add_inst(name="pnor2_pmos1",
                                      mod=self.pmos,
                                      offset=pmos1_pos)
        self.connect_inst(["vdd", "A", "net1", "vdd"])

        self.pmos2_pos = pmos1_pos + self.overlap_offset
        self.pmos2_inst = self.add_inst(name="pnor2_pmos2",
                                        mod=self.pmos2,
                                        offset=self.pmos2_pos)
        self.connect_inst(["net1", "B", "Z", "vdd"])

        # place NMOS so that its implant aligns with cell boundary
        nmos_y_offset = -self.nmos.implant_rect.offset.y
        nmos1_pos = vector(x_offset, nmos_y_offset)
       
        self.nmos1_inst=self.add_inst(name="pnor2_nmos1",
                                      mod=self.nmos,
                                      offset=nmos1_pos)
        self.connect_inst(["Z", "A", "gnd", "gnd"])

        self.nmos2_pos = nmos1_pos + self.overlap_offset
        self.nmos2_inst=self.add_inst(name="pnor2_nmos2",
                                      mod=self.nmos2,
                                      offset=self.nmos2_pos)
        self.connect_inst(["Z", "B", "gnd", "gnd"])
        
        self.output_pos = vector(0,utils.ceil(0.5*(self.height-self.pmos.height + self.nmos.height)))    
        
        # This will help with the wells 
        self.well_pos = vector(0, self.output_pos.y)
        
    def connect_rails(self):
        """ Connect the nmos and pmos to its respective power rails """

        self.connect_pin_to_rail(self.nmos1_inst,"S","gnd")

        self.connect_pin_to_rail(self.nmos2_inst,"D","gnd")

        self.connect_pin_to_rail(self.pmos1_inst,"S","vdd")


    def route_inputs(self):
        """ Route the A and B inputs """
        inputB_yoffset = self.output_pos.y - self.wide_m1_space - 0.5*self.max_input_width
        self.route_input_gate(self.pmos2_inst, self.nmos2_inst, inputB_yoffset, "B", position="center")
        
        self.inputA_yoffset = self.output_pos.y + self.wide_m1_space + 0.5*self.max_input_width
        self.route_input_gate(self.pmos1_inst, self.nmos1_inst, self.inputA_yoffset, "A")

    def route_output(self):
        """ Route the Z output """
        # PMOS1 drain 
        pmos_pin = self.pmos2_inst.get_pin("D")
        # NMOS2 drain
        nmos_pin = self.nmos1_inst.get_pin("D")        
        # Output pin
        mid_offset = vector(pmos_pin.center().x + drc["nand_output_offset"], self.output_pos.y)
        self.add_path("metal2",[pmos_pin.center(), mid_offset, nmos_pin.center()])

        self.add_contact_center(layers=("metal1", "via1", "metal2"),
                                offset=pmos_pin.center())

        metal1_contact_area = self.pmos.active_contact.second_layer_height*self.pmos.active_contact.second_layer_width
        if metal1_contact_area < self.pmos.minarea_metal1_contact :
            # add extra metal1 to nmos2 drain to fulfill drc requirement
            fill_height = self.pmos2.active_contact.second_layer_height
            fill_width = utils.ceil(drc["minarea_metal1_contact"]/fill_height)
            self.add_rect(layer="metal1",
                        offset=pmos_pin.ll(),
                        height=fill_height,
                        width=fill_width)

        output_pin_offset = mid_offset - vector(0, 0.5*contact.m1m2.second_layer_height)
        # This extends the output to the edge of the cell
        self.add_contact_center(layers=("metal1", "via1", "metal2"),
                                offset=output_pin_offset)

        # minimum area rules for metal1 output
        self.output_width = contact.m1m2.first_layer_height
        self.output_height = utils.ceil(drc["minarea_metal1_contact"]/self.output_width)

        self.add_layout_pin_center_rect(text="Z",
                                        layer="metal1",
                                        offset=output_pin_offset,
                                        width=self.output_width,
                                        height=self.output_height)


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
        power_leak = spice["nor2_leakage"]
        
        total_power = self.return_power(power_dyn, power_leak)
        return total_power
        
    def calculate_effective_capacitance(self, load):
        """Computes effective capacitance. Results in fF"""
        c_load = load
        c_para = spice["min_tx_drain_c"]*(self.nmos_size/parameter["min_tx_size"])#ff
        transistion_prob = spice["nor2_transisition_prob"]
        return transistion_prob*(c_load + c_para) 
        