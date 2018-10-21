import contact
import pgate
import debug
from tech import drc, parameter, spice, info
from ptx import ptx
from ptx_spice import ptx_spice
from vector import vector
from globals import OPTS
import unique_meta
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
    __metaclass__ = unique_meta.Unique

    c = __import__(OPTS.bitcell)
    bitcell = getattr(c, OPTS.bitcell)

    @classmethod
    def get_name(cls, size=1, beta=parameter["beta"], height=pgate.pgate.get_default_height(),
                 contact_pwell=True, contact_nwell=True, align_bitcell=False):
        name = "pinv_{}".format(size)
        if align_bitcell:
            height = pinv.bitcell.height
        if not contact_pwell:
            name += "_no_p"
        if not contact_nwell:
            name += "_no_n"
        if not beta == parameter["beta"]:
            name += "_b" + str(beta)
        if not height == pgate.pgate.get_default_height():
            name += "_h_" + str(height).replace(".", "_")
        if align_bitcell:
            name += "_align"
        return name



    def __init__(self, size=1, beta=parameter["beta"], height=pgate.pgate.get_default_height(),
                 contact_pwell=True, contact_nwell=True, align_bitcell=False):
        # We need to keep unique names because outputting to GDSII
        # will use the last record with a given name. I.e., you will
        # over-write a design in GDS if one has and the other doesn't
        # have poly connected, for example.

        pgate.pgate.__init__(self, self.name, height, size=size, beta=beta, contact_pwell=contact_pwell,
                             contact_nwell=contact_nwell, align_bitcell=align_bitcell)
        debug.info(2, "create pinv structure {0} with size of {1}".format(self.name, size))

        self.add_pins()
        self.create_layout()

        # for run-time, we won't check every transitor DRC/LVS independently
        # but this may be uncommented for debug purposes
        #self.DRC_LVS()

    def add_pins(self):
        """ Adds pins for spice netlist """
        self.add_pin_list(["A", "Z", "vdd", "gnd"])
        

    def create_layout(self):

        self.nmos_scale = 1
        self.pmos_scale = 1
        self.no_tracks = 1

        self.determine_tx_mults()
        self.setup_layout_constants()
        self.add_poly()
        self.add_poly_contacts()
        self.add_active()
        self.calculate_source_drain_pos()
        self.connect_to_vdd(self.source_positions)
        self.connect_to_gnd(self.source_positions)
        self.connect_s_or_d(self.drain_positions, self.drain_positions)
        self.add_implants()
        self.add_body_contacts()
        self.add_output_pin()
        self.add_ptx_inst()



    def add_poly_contacts(self):
        if self.tx_mults == 1:
            width = utils.ceil(max(self.minarea_metal1_contact/contact.poly.second_layer_height,
                                      self.minside_metal1_contact))
            offset = vector(self.mid_x, self.mid_y)
            self.add_layout_pin_center_rect("A", "metal1", offset, width=width, height=contact.poly.second_layer_height)
            offset = vector(self.mid_x, self.mid_y)
            self.add_contact_center(layers=("poly", "contact", "metal1"), offset=offset)

        else:
            contact_width = contact.poly.second_layer_width
            for i in range(len(self.poly_offsets)):
                offset = vector(self.poly_offsets[i].x, self.mid_y)
                self.add_contact_center(layers=("poly", "contact", "metal1"), offset=offset)
                self.add_rect_center("metal1", offset=offset, height=contact.poly.second_layer_height,
                                     width=contact_width)
            min_poly = min(self.poly_offsets, key=lambda x: x.x).x
            max_poly = max(self.poly_offsets, key=lambda x: x.x).x
            pin_left = min_poly - 0.5*contact_width
            pin_right = max_poly + 0.5*contact_width
            offset = vector(0.5*(pin_left + pin_right), self.mid_y)
            self.add_layout_pin_center_rect("A", "metal1", offset, width=pin_right-pin_left)



    def add_ptx_inst(self):
        self.pmos = ptx_spice(self.pmos_width, mults=self.tx_mults, tx_type="pmos")
        self.add_inst(name="pinv_pmos",
                      mod=self.pmos,
                      offset=vector(0, 0))
        self.add_mod(self.pmos)
        self.connect_inst(["Z", "A", "vdd", "vdd"])
        self.nmos = ptx_spice(self.nmos_width, mults=self.tx_mults, tx_type="nmos")
        self.add_inst(name="pinv_nmos",
                      mod=self.nmos,
                      offset=vector(0, 0))
        self.add_mod(self.nmos)
        self.connect_inst(["Z", "A", "gnd", "gnd"])


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