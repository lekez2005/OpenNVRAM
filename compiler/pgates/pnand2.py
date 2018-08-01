import contact
import pgate
import debug
from tech import drc, parameter, spice
from ptx import ptx
from vector import vector
from globals import OPTS
import utils

class pnand2(pgate.pgate):
    """
    This module generates gds of a parametrically sized 2-input nand.
    This model use ptx to generate a 2-input nand within a cetrain height.
    """

    c = reload(__import__(OPTS.bitcell))
    bitcell = getattr(c, OPTS.bitcell)

    unique_id = 1
    
    def __init__(self, size=1, height=bitcell.height):
        """ Creates a cell for a simple 2 input nand """
        name = "pnand2_{0}".format(pnand2.unique_id)
        pnand2.unique_id += 1
        pgate.pgate.__init__(self, name)
        debug.info(2, "create pnand2 structure {0} with size of {1}".format(name, size))

        self.nmos_size = 2*size
        self.pmos_size = parameter["beta"]*size
        self.nmos_width = self.nmos_size*drc["minwidth_tx"]
        self.pmos_width = self.pmos_size*drc["minwidth_tx"]
        self.height = height

        self.add_pins()
        self.create_layout()
        #self.DRC_LVS()

        
    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "B", "Z", "vdd", "gnd"])

    def create_layout(self):
        """ Calls all functions related to the generation of the layout """
        self.determine_tx_mults()
        # FIXME: Allow multiple fingers
        debug.check(self.tx_mults==1,
            "Only Single finger {} is supported now.".format(self.__class__.__name__))

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


        # metal spacing to allow contacts on any layer
        self.max_input_width = max(contact.m1m2.first_layer_width,
                                 contact.m2m3.first_layer_width, contact.m2m3.second_layer_width)
        self.input_spacing = self.max_input_width + self.wide_m1_space
        # pmos gate contact to A input to B input to nmos gate contact
        self.min_channel = 3*self.input_spacing
        pgate.pgate.determine_tx_mults(self)

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

    def setup_layout_constants(self):
        """ Pre-compute some handy layout parameters. """
 
        # Compute the other pmos2 location, but determining offset to overlap the
        # source and drain pins
        self.overlap_offset = vector(self.pmos.contact_pitch, 0)

        tx_width = 5*self.pmos.poly_pitch + self.pmos.poly_width

        # the well width is determined the multi-finger PMOS device width plus
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

        x_offset = 0.5*(self.pmos.width-self.pmos.active_width)

        #place PMOS so that its implant aligns with cell boundary
        # account for active_offset translation that happens after creation

        active_to_bottom_implant = self.pmos.active_offset.y - self.pmos.implant_offset.y
        active_bottom_to_top_implant = self.pmos.implant_height - active_to_bottom_implant

        pmos_bottom = self.height - (self.pmos.implant_rect.offset.y + self.pmos.implant_rect.height)
        pmos1_pos = vector(x_offset, pmos_bottom)
        self.pmos1_inst=self.add_inst(name="pnand2_pmos1",
                                      mod=self.pmos,
                                      offset=pmos1_pos)
        self.connect_inst(["vdd", "A", "Z", "vdd"])

        self.pmos2_pos = pmos1_pos + self.overlap_offset
        self.pmos2_inst = self.add_inst(name="pnand2_pmos2",
                                        mod=self.pmos2,
                                        offset=self.pmos2_pos)
        self.connect_inst(["Z", "B", "vdd", "vdd"])


        # place NMOS so that its implant aligns with cell boundary

        nmos_y_offset = -self.nmos.implant_rect.offset.y
        nmos1_pos = vector(x_offset, nmos_y_offset)
        self.nmos1_inst=self.add_inst(name="pnand2_nmos1",
                                      mod=self.nmos,
                                      offset=nmos1_pos)
        self.connect_inst(["Z", "B", "net1", "gnd"])

        self.nmos2_pos = nmos1_pos + self.overlap_offset
        self.nmos2_inst=self.add_inst(name="pnand2_nmos2",
                                      mod=self.nmos2,
                                      offset=self.nmos2_pos)
        self.connect_inst(["net1", "A", "gnd", "gnd"])

        self.output_pos = vector(0,utils.ceil(0.5*(self.height-self.pmos.height + self.nmos.height)))

        # This will help with the wells
        self.well_pos = vector(0, self.output_pos.y)

    def add_well_contacts(self):
        """ Add n/p well taps to the layout and connect to supplies AFTER the wells are created """

        self.add_nwell_contact(self.pmos, self.pmos2_pos, size=[1, 3])
        self.add_pwell_contact(self.nmos, self.nmos2_pos, size=[1, 3])


    def connect_rails(self):
        """ Connect the nmos and pmos to its respective power rails """

        self.connect_pin_to_rail(self.nmos1_inst,"S","gnd")

        self.connect_pin_to_rail(self.pmos1_inst,"S","vdd")

        self.connect_pin_to_rail(self.pmos2_inst,"D","vdd")

    def route_inputs(self):
        """ Route the A and B inputs """
        inputB_yoffset = self.output_pos.y - self.wide_m1_space - self.m1_width
        self.route_input_gate(self.pmos2_inst, self.nmos2_inst, inputB_yoffset, "B", position="center")

        self.inputA_yoffset = self.output_pos.y + self.wide_m1_space + self.m1_width
        self.route_input_gate(self.pmos1_inst, self.nmos1_inst, self.inputA_yoffset, "A", position="center")


    def route_output(self):
        """ Route the Z output """
        layers = ("metal1", "via1", "metal2")
        # PMOS1 drain
        pmos_pin = self.pmos1_inst.get_pin("D")
        # NMOS2 drain
        nmos_pin = self.nmos2_inst.get_pin("D")

        gate_pin = self.nmos2_inst.get_pin("G")

        min_output_separation = drc["min_output_separation"]
        output_x = gate_pin.rx() + min_output_separation

        self.add_contact(layers=layers, offset=nmos_pin.ll()+vector(drc["metal2_extend_via2"], 0))

        self.add_rect(layer="metal2", offset=nmos_pin.ll(), height=contact.m1m2.second_layer_height,
                      width=output_x-nmos_pin.lx())
        self.add_rect(layer="metal2", offset=pmos_pin.ll(), height=contact.m1m2.second_layer_height,
                      width=output_x-pmos_pin.lx())

        top_via = self.pmos2_inst.get_pin("G").center().y - 0.5*contact.poly.second_layer_height \
                  - self.wide_m1_space - contact.m1m2.first_layer_height
        top_via_offset = vector(output_x - contact.m1m2.second_layer_width, top_via)
        self.add_contact(layers, top_via_offset)

        bottom_via = self.nmos2_inst.get_pin("G").center().y + 0.5 * contact.poly.second_layer_height \
                     + self.wide_m1_space
        bottom_via_offset = vector(output_x - contact.m1m2.second_layer_width, bottom_via)
        self.add_contact(layers, bottom_via_offset)

        bot_rect_offset = vector(output_x-self.m2_width, nmos_pin.by())
        self.add_rect(layer="metal2", width=self.m2_width, height=bottom_via_offset.y-bot_rect_offset.y,
                      offset=bot_rect_offset)
        self.add_rect(layer="metal2", width=self.m2_width, height=pmos_pin.by()-top_via, offset=top_via_offset)

        self.add_rect(layer="metal1", width=self.m1_width, offset=bottom_via_offset, height=top_via-bottom_via)

        pin_pos = vector(output_x-0.5*self.m1_width, self.output_pos.y)

        self.add_layout_pin_center_rect(text="Z",
                                        layer="metal1",
                                        offset=pin_pos)

        metal1_contact_area = self.nmos.active_contact.second_layer_height * self.nmos.active_contact.second_layer_width
        if metal1_contact_area < self.nmos.minarea_metal1_contact:
            # add extra metal1 to nmos2 drain to fulfill drc requirement
            fill_height = max(self.nmos.active_contact.second_layer_height, contact.m1m2.second_layer_height)
            fill_width = utils.ceil(drc["minarea_metal1_contact"] / fill_height)
            self.add_rect(layer="metal1",
                          offset=nmos_pin.ll(),
                          height=fill_height,
                          width=fill_width)




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
        power_leak = spice["nand2_leakage"]
        
        total_power = self.return_power(power_dyn, power_leak)
        return total_power
        
    def calculate_effective_capacitance(self, load):
        """Computes effective capacitance. Results in fF"""
        c_load = load
        c_para = spice["min_tx_drain_c"]*(self.nmos_size/parameter["min_tx_size"])#ff
        transistion_prob = spice["nand2_transisition_prob"]
        return transistion_prob*(c_load + c_para) 
