import contact
import pgate
import debug
from tech import drc, parameter, spice, info
from ptx import ptx
from vector import vector
from globals import OPTS
from utils import round_to_grid
import utils

class pinv(pgate.pgate):
    """
    Pinv generates gds of a parametrically sized inverter. The
    size is specified as the drive size (relative to minimum NMOS) and
    a beta value for choosing the pmos size.  The inverter's cell
    height is usually the same as the 6t library cell and is measured
    from center of rail to rail..  The route_output will route the
    output to the right side of the cell for easier access.
    """
    c = reload(__import__(OPTS.bitcell))
    bitcell = getattr(c, OPTS.bitcell)

    unique_id = 1
    
    def __init__(self, size=1, beta=parameter["beta"], height=bitcell.height, route_output=True):
        # We need to keep unique names because outputting to GDSII
        # will use the last record with a given name. I.e., you will
        # over-write a design in GDS if one has and the other doesn't
        # have poly connected, for example.
        name = "pinv_{}".format(pinv.unique_id)
        pinv.unique_id += 1
        pgate.pgate.__init__(self, name)
        debug.info(2, "create pinv structure {0} with size of {1}".format(name, size))

        self.nmos_size = size
        self.pmos_size = beta*size
        self.beta = beta
        self.height = height # Maybe minimize height if not defined in future?
        self.route_output = route_output

        self.add_pins()
        self.create_layout()

        # for run-time, we won't check every transitor DRC/LVS independently
        # but this may be uncommented for debug purposes
        #self.DRC_LVS()

    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "Z", "vdd", "gnd"])
        
    def create_layout(self):
        """ Calls all functions related to the generation of the layout """

        self.determine_tx_mults()
        self.create_ptx()
        self.setup_layout_constants()
        self.add_supply_rails()
        self.add_ptx()
        self.add_well_contacts()
        self.extend_wells(self.well_pos)
        self.connect_rails()
        self.route_input_gate(self.pmos_inst, self.nmos_inst, self.output_pos.y, "A",
                              rotate=0, position="center")
        self.route_outputs()
        
    def determine_tx_mults(self):
        self.output_height = self.m1_width
        self.min_channel = self.m1_space + max(drc["implant_to_implant"], self.output_height)
        pgate.pgate.determine_tx_mults(self)

    def setup_layout_constants(self):
        """
        Pre-compute some handy layout parameters.
        """

        # the well width is determined the multi-finger PMOS device width plus
        # the well contact width and half well enclosure on both sides
        well_contact = contact.contact(layer_stack=("cont_active", "contact", "cont_metal1"), 
                                implant_type="n",
                                well_type="n")
        # width of active and one side of enclosure of well around active
        active_implant_width = well_contact.first_layer_width + drc["well_enclosure_active"]
        self.well_width = self.pmos.width + drc["poly_dummy_to_active"] +  active_implant_width
        self.width = self.well_width
        # Height is an input parameter, so it is not recomputed. 
        

        
    def create_ptx(self):
        """ Create the PMOS and NMOS transistors. """
        self.nmos = ptx(width=self.nmos_width,
                        mults=self.tx_mults,
                        tx_type="nmos",
                        connect_poly=True,
                        connect_active=True)
        self.add_mod(self.nmos)
        
        self.pmos = ptx(width=self.pmos_width,
                        mults=self.tx_mults,
                        tx_type="pmos",
                        connect_poly=True,
                        connect_active=True)
        self.add_mod(self.pmos)
        
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
        x_offset = 0.5*(self.pmos.width-self.pmos.active_width)
        
        # place PMOS so that its implant aligns with cell boundary
        # account for active_offset translation that happens after creation
        pmos_bottom = self.height - (self.pmos.implant_rect.offset.y + self.pmos.implant_rect.height)
        self.pmos_pos = vector(x_offset, pmos_bottom)
        self.pmos_inst=self.add_inst(name="pinv_pmos",
                                     mod=self.pmos,
                                     offset=self.pmos_pos)
        self.connect_inst(["Z", "A", "vdd", "vdd"])

        # place NMOS so that its implant aligns with cell boundary
        nmos_y_offset = -self.nmos.implant_rect.offset.y
        self.nmos_pos = vector(x_offset, nmos_y_offset)
        self.nmos_inst=self.add_inst(name="pinv_nmos",
                                     mod=self.nmos,
                                     offset=self.nmos_pos)
        self.connect_inst(["Z", "A", "gnd", "gnd"])


        # Output position will be in between the PMOS and NMOS drains
        pmos_drain_pos = self.pmos_inst.get_pin("D").ll()
        nmos_drain_pos = self.nmos_inst.get_pin("D").ul()
        self.output_pos = vector(0,0.5*(pmos_drain_pos.y+nmos_drain_pos.y))

        # This will help with the wells 
        nmos_top = self.nmos_inst.height
        pmos_bottom = self.height - self.pmos_inst.height
        self.well_pos = vector(0, round_to_grid(0.5*(nmos_top + pmos_bottom)))
        


    def route_outputs(self):
        """ Route the output (drains) together. Optionally, routes output to edge. """
        layers=("metal1", "via1", "metal2")
        min_output_separation = drc["min_output_separation"]
        # Get the drain pins
        nmos_drain_pin = self.nmos_inst.get_pin("D")
        pmos_drain_pin = self.pmos_inst.get_pin("D")
        gate_pin = self.pmos_inst.get_pin("G")

        output_x = pmos_drain_pin.rx()
        if nmos_drain_pin.rx() < gate_pin.lx() + min_output_separation:
            output_x = gate_pin.lx() + min_output_separation - self.m2_width
            self.add_rect(layer="metal2", offset=pmos_drain_pin.lr(), height=pmos_drain_pin.height(),
                          width=output_x-pmos_drain_pin.rx())
            self.add_rect(layer="metal2", offset=nmos_drain_pin.lr(), height=nmos_drain_pin.height(),
                          width=output_x-nmos_drain_pin.rx())


        top_via = self.pmos_inst.get_pin("G").center().y - 0.5*contact.poly.second_layer_height \
                  - self.wide_m1_space - contact.m1m2.first_layer_height
        top_via_offset = vector(output_x - contact.m1m2.second_layer_width, top_via)
        self.add_contact(layers, top_via_offset)

        bottom_via = self.nmos_inst.get_pin("G").center().y + 0.5*contact.poly.second_layer_height \
                     + self.wide_m1_space
        bottom_via_offset = vector(output_x - contact.m1m2.second_layer_width, bottom_via)
        self.add_contact(layers, bottom_via_offset)

        nmos_drain_pos = vector(output_x-self.m2_width, nmos_drain_pin.uy())
        pmos_drain_pos = vector(output_x-self.m2_width, pmos_drain_pin.by())

        pmos_connection_height = pmos_drain_pos.y-top_via
        self.add_rect(layer="metal2", offset=pmos_drain_pos-vector(0, pmos_connection_height),
                      width=self.m2_width, height=pmos_connection_height)
        self.add_rect(layer="metal2", offset=nmos_drain_pos, width=self.m2_width, height=bottom_via-nmos_drain_pos.y)

        self.add_rect(layer="metal1", offset=bottom_via_offset, width=self.m1_width,
                      height=top_via_offset.y-bottom_via_offset.y)


        # Remember the mid for the output
        mid_drain_offset = vector(output_x-0.5*self.m1_width, self.output_pos.y)

        if self.route_output == True:
            # This extends the output to the edge of the cell
            output_offset = mid_drain_offset.scale(0,1) + vector(self.width,0)
            self.add_layout_pin_center_segment(text="Z",
                                               layer="metal1",
                                               start=mid_drain_offset,
                                               end=output_offset)
        else:
            self.add_layout_pin_center_rect(text="Z",
                                            layer="metal1",
                                            height=self.output_height,
                                            offset=mid_drain_offset)


    def add_well_contacts(self):
        """ Add n/p well taps to the layout and connect to supplies """

        self.add_nwell_contact(self.pmos, self.pmos_pos, size=[1, 3])

        self.add_pwell_contact(self.nmos, self.nmos_pos, size=[1, 3])

    def connect_rails(self):
        """ Connect the nmos and pmos to its respective power rails """

        self.connect_pin_to_rail(self.nmos_inst,"S","gnd")

        self.connect_pin_to_rail(self.pmos_inst,"S","vdd")
        

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
        power_leak = spice["inv_leakage"]
        
        total_power = self.return_power(power_dyn, power_leak)
        return total_power
        
    def calculate_effective_capacitance(self, load):
        """Computes effective capacitance. Results in fF"""
        c_load = load
        c_para = spice["min_tx_drain_c"]*(self.nmos_size/parameter["min_tx_size"])#ff
        transistion_prob = spice["inv_transisition_prob"]
        return transistion_prob*(c_load + c_para) 