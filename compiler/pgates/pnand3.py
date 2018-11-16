import contact
import pgate
import debug
from tech import drc, parameter, spice
from ptx_spice import ptx_spice
from vector import vector
from globals import OPTS
import utils

class pnand3(pgate.pgate):
    """
    This module generates gds of a parametrically sized 3-input nand.
    This model use ptx to generate a 3-input nand within a certain height.
    """

    c = __import__(OPTS.bitcell)
    bitcell = getattr(c, OPTS.bitcell)

    unique_id = 1
    
    def __init__(self, size=1, height=pgate.pgate.get_default_height(), contact_pwell=True, contact_nwell=True,
                 align_bitcell=False, same_line_inputs=True):
        """ Creates a cell for a simple 3 input nand """
        name = "pnand3_{0}".format(pnand3.unique_id)
        pnand3.unique_id += 1
        pgate.pgate.__init__(self, name, height, size=size, contact_pwell=contact_pwell, contact_nwell=contact_nwell,
                             align_bitcell=align_bitcell, same_line_inputs=same_line_inputs)
        debug.info(2, "create pnand3 structure {0} with size of {1}".format(name, size))

        self.add_pins()
        self.create_layout()
        #self.DRC_LVS()

        
    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "B", "C", "Z", "vdd", "gnd"])

    def create_layout(self):
        """ Calls all functions related to the generation of the layout """
        self.nmos_scale = 2.5  # should ideally be 3 but need to implement multi-finger
        self.pmos_scale = 1
        self.no_tracks = 3

        self.shrink_if_needed()

        self.determine_tx_mults()
        # FIXME: Allow multiple fingers
        debug.check(self.tx_mults==1,"Only Single finger pnand3 is supported now.")
        self.tx_mults *= 3

        self.setup_layout_constants()
        self.add_poly()
        self.connect_inputs()

        self.add_active()
        self.calculate_source_drain_pos()

        self.connect_to_vdd(self.source_positions)
        self.connect_to_gnd(self.source_positions[0:1])
        self.connect_s_or_d(self.drain_positions, self.drain_positions[1:])
        self.add_implants()
        self.add_body_contacts()
        self.add_output_pin()
        self.add_ptx_inst()

    def connect_inputs(self):
        y_shifts = [-self.gate_rail_pitch, 0, self.gate_rail_pitch]
        pin_names = ["A", "B", "C"]
        self.add_poly_contacts(pin_names, y_shifts)

    def add_ptx_inst(self):
        offset = vector(0, 0)
        self.pmos = ptx_spice(self.pmos_width, mults=self.tx_mults/3, tx_type="pmos")
        self.pmos1_inst = self.add_inst(name="pnand3_pmos1", mod=self.pmos, offset=offset)
        self.connect_inst(["vdd", "A", "Z", "vdd"])

        self.pmos2_inst = self.add_inst(name="pnand3_pmos2", mod=self.pmos, offset=offset)
        self.connect_inst(["Z", "B", "vdd", "vdd"])

        self.pmos3_inst = self.add_inst(name="pnand3_pmos3", mod=self.pmos, offset=offset)
        self.connect_inst(["Z", "C", "vdd", "vdd"])

        self.nmos = ptx_spice(self.nmos_width, mults=self.tx_mults/3, tx_type="nmos")
        self.nmos1_inst = self.add_inst(name="pnand3_nmos1", mod=self.nmos, offset=offset)
        self.connect_inst(["Z", "C", "net1", "gnd"])

        self.nmos2_inst = self.add_inst(name="pnand3_nmos2", mod=self.nmos, offset=offset)
        self.connect_inst(["net1", "B", "net2", "gnd"])

        self.nmos3_inst = self.add_inst(name="pnand3_nmos3", mod=self.nmos, offset=offset)
        self.connect_inst(["net2", "A", "gnd", "gnd"])


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
