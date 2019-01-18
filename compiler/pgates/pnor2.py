import debug
from base.vector import vector
from globals import OPTS
from tech import parameter, spice
from . import pgate
from .ptx_spice import ptx_spice


class pnor2(pgate.pgate):
    """
    This module generates gds of a parametrically sized 2-input nor.
    This model use ptx to generate a 2-input nor within a cetrain height.
    """

    c = __import__(OPTS.bitcell)
    bitcell = getattr(c, OPTS.bitcell)

    unique_id = 1
    
    def __init__(self, size=1, height=pgate.pgate.get_default_height(), contact_pwell=True, contact_nwell=True):
        """ Creates a cell for a simple 2 input nor """
        name = "pnor2_{0}".format(pnor2.unique_id)
        pnor2.unique_id += 1
        pgate.pgate.__init__(self, name, height, size=size, contact_pwell=contact_pwell, contact_nwell=contact_nwell)
        debug.info(2, "create pnor2 structure {0} with size of {1}".format(name, size))

        self.add_pins()
        self.create_layout()
        #self.DRC_LVS()

    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "B", "Z", "vdd", "gnd"])

    def create_layout(self):
        self.nmos_scale = 1
        self.pmos_scale = 2
        self.no_tracks = 2

        self.determine_tx_mults()
        # FIXME: Allow multiple fingers
        debug.check(self.tx_mults == 1,
                    "Only Single finger {} is supported now.".format(self.__class__.__name__))

        self.tx_mults *= 2

        self.setup_layout_constants()
        self.add_poly()
        self.connect_inputs()

        self.add_active()
        self.calculate_source_drain_pos()

        self.connect_to_vdd(self.source_positions[0:1])
        self.connect_to_gnd(self.source_positions)
        self.connect_s_or_d(self.source_positions[1:], self.drain_positions)
        self.add_implants()
        self.add_body_contacts()
        self.add_output_pin()
        self.add_ptx_inst()

    def connect_inputs(self):
        y_shifts = [-0.5*self.gate_rail_pitch, 0.5*self.gate_rail_pitch]
        pin_names = ["A", "B"]
        self.add_poly_contacts(pin_names, y_shifts)

    def add_ptx_inst(self):
        offset = vector(0, 0)
        self.pmos = ptx_spice(self.pmos_width, mults=self.tx_mults/2, tx_type="pmos")
        self.pmos1_inst = self.add_inst(name="pnor2_pmos1",
                                        mod=self.pmos,
                                        offset=offset)
        self.connect_inst(["vdd", "A", "net1", "vdd"])

        self.pmos2_inst = self.add_inst(name="pnor2_pmos2",
                                        mod=self.pmos,
                                        offset=offset)
        self.connect_inst(["net1", "B", "Z", "vdd"])

        self.nmos = ptx_spice(self.nmos_width, mults=self.tx_mults/2, tx_type="nmos")
        self.nmos1_inst = self.add_inst(name="pnor2_nmos1",
                                        mod=self.nmos,
                                        offset=offset)
        self.connect_inst(["Z", "A", "gnd", "gnd"])

        self.nmos2_inst = self.add_inst(name="pnor2_nmos2",
                                        mod=self.nmos,
                                        offset=offset)
        self.connect_inst(["Z", "B", "gnd", "gnd"])




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
        