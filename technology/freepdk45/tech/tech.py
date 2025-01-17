import os

"""
File containing the process technology parameters for FreePDK 45nm.
"""


def add_tech_layers(obj):
    for layer_ in ["nwell", "pwell"]:
        for well_rect in obj.get_layer_shapes(layer_):
            width = well_rect.rx() - well_rect.lx()
            height = well_rect.uy() - well_rect.by()
            obj.add_rect("vtg", offset=well_rect.ll(), width=width, height=height)


def delay_params_class():
    try:
        from delay_params import DelayParams
    except ImportError:
        from .delay_params import DelayParams
    return DelayParams


info = {}
info["name"] = "freepdk45"
info["body_tie_down"] = 0
info["has_pwell"] = True
info["has_nwell"] = True
info["poly_contact_layer"] = "metal1"

#GDS file info
GDS = {}
# gds units
GDS["unit"] = (0.0005,1e-9)
# default label zoom
GDS["zoom"] = 0.05

###################################################
##GDS Layer Map
###################################################

# create the GDS layer map
# FIXME: parse the gds layer map from the cadence map?
layer = {}
layer["active"]  = 1
layer["pwell"]   = 2
layer["nwell"]   = 3
layer["nimplant"]= 4
layer["pimplant"]= 5
layer["vtg"]     = 6
layer["vth"]     = 7
layer["thkox"]   = 8
layer["poly"]    = 9
layer["contact"] = 10
layer["active_contact"] = 10
layer["metal1"]  = 11
layer["via1"]    = 12
layer["metal2"]  = 13
layer["via2"]    = 14
layer["metal3"]  = 15
layer["via3"]    = 16
layer["metal4"]  = 17
layer["via4"]    = 18
layer["metal5"]  = 19
layer["via5"]    = 20
layer["metal6"]  = 21
layer["via6"]    = 22
layer["metal7"]  = 23
layer["via7"]    = 24
layer["metal8"]  = 25
layer["via8"]    = 26
layer["metal9"]  = 27
layer["via9"]    = 28
layer["metal10"] = 29
layer["text"]    = 239
layer["boundary"]= 239

purpose = {"drawing": 0}

layer_colors = {
    "vtg": ("#00ccf2", "outline"),
    "text": ("#9900e6", "dashed")
}


default_fill_layers = ["nwell", "nimplant", "pimplant", "pwell"]

power_grid_layers = ["metal9", "metal10"]
power_grid_num_vias = 2

###################################################
##END GDS Layer Map
###################################################

###################################################
##DRC/LVS Rules Setup
###################################################

#technology parameter
parameter={}
parameter["min_tx_size"] = 0.09
parameter["beta"] = 1.52

drclvs_home=os.environ.get("DRCLVS_HOME")
drc={}
#grid size
drc["grid"] = 0.0025

#DRC/LVS test set_up
drc["drc_rules"]=drclvs_home+"/calibreDRC.rul"
drc["lvs_rules"]=drclvs_home+"/calibreLVS.rul"
drc["xrc_rules"]=drclvs_home+"/calibrexRC.rul"
drc["layer_map"]=os.environ.get("OPENRAM_TECH")+"/freepdk45/layers.map"

drc["latchup_spacing"] = 40  # not an enforced rule but realistically needed

# minwidth_tx with contact (no dog bone transistors)
drc["minwidth_tx"]=0.09
drc["maxwidth_tx"] = 4
drc["minlength_channel"] = 0.05

# for metal buses
drc["medium_width"] = 0.08
drc["bus_space"] = 0.08

# WELL.1 Minimum spacing of nwell/pwell at different potential
drc["pwell_to_nwell"] = 0.225
drc["nwell_to_nwell"] = 0.0
drc["pwell_to_pwell"] = 0.0
# WELL.4 Minimum width of nwell/pwell
drc["minwidth_well"] = 0.2

# POLY.1 Minimum width of poly
drc["minwidth_poly"] = 0.05
# POLY.2 Minimum spacing of poly AND active
drc["poly_to_poly"] = 0.14
# space between vertical ends of poly
drc["poly_end_to_end"] = 0.075
# POLY.3 Minimum poly extension beyond active
drc["poly_extend_active"] = 0.055
# POLY.4 Minimum enclosure of active around gate
drc["active_enclosure_gate"] = 0.07
# POLY.5 Minimum spacing of field poly to active
drc["poly_to_active"] = 0.05
# POLY.6 Minimum Minimum spacing of field poly
drc["poly_to_field_poly"] = 0.075

drc["poly_contact_to_active"] = 0.055
# Not a rule
drc["minarea_poly"] = 0.0

# ACTIVE.2 Minimum spacing of active
drc["active_to_body_active"] = 0.08
drc["active_to_body_active"] = 0.105 # account for poly extension to the active
# ACTIVE.1 Minimum width of active
drc["minwidth_active"] = 0.09
# Not a rule
drc["active_to_active"] = 0
# ACTIVE.3 Minimum enclosure/spacing of nwell/pwell to active
drc["well_enclosure_active"] = 0.055
# Reserved for asymmetric enclosures
drc["well_extend_active"] = 0.055
# Not a rule
drc["minarea_active"] = 0
drc["nwell_to_active_space"] = 0.07

# IMPLANT.1 Minimum spacing of nimplant/ pimplant to channel
drc["implant_to_channel"] = 0.07
# Not a rule
drc["implant_enclosure_active"] = 0
# Not a rule
drc["implant_enclosure_contact"] = 0
# IMPLANT.2 Minimum spacing of nimplant/ pimplant to contact
drc["implant_to_contact"] = 0.025
# IMPLANT.3 Minimum width/ spacing of nimplant/ pimplant
drc["implant_to_implant"] = 0.045
# IMPLANT.4 Minimum width/ spacing of nimplant/ pimplant
drc["minwidth_implant"] = 0.045

# CONTACT.1 Minimum width of contact
drc["minwidth_contact"] = 0.065
# CONTACT.2 Minimum spacing of contact
drc["contact_to_contact"] = 0.075
# CONTACT.4 Minimum enclosure of active around contact
drc["active_enclosure_contact"] = 0.005
# Reserved for asymmetric enclosures
drc["active_extend_contact"] = 0.005
# CONTACT.5 Minimum enclosure of poly around contact
drc["poly_enclosure_contact"] = 0.005
# Reserved for asymmetric enclosures
drc["poly_extend_contact"] = 0.005
# CONTACT.6 Minimum spacing of contact and gate
drc["contact_to_gate"] = 0.0375 #changed from 0.035

# METAL1.1 Minimum width of metal1
drc["minwidth_metal1"] = 0.065
# METAL1.2 Minimum spacing of metal1
drc["metal1_to_metal1"] = 0.065
# METAL1.3 Minimum enclosure around contact on two opposite sides
drc["metal1_enclosure_contact"] = 0
# Reserved for asymmetric enclosures
drc["metal1_extend_contact"] = 0.035
# METAL1.4 inimum enclosure around via1 on two opposite sides
drc["metal1_extend_via1"] = 0.035
# Reserved for asymmetric enclosures
drc["metal1_enclosure_via1"] = 0
# Not a rule
drc["minarea_metal1"] = 0

# VIA1.1 Minimum width of via1
drc["minwidth_via1"] = 0.065
# VIA1.2 Minimum spacing of via1
drc["via1_to_via1"] = 0.075

# METALINT.1 Minimum width of intermediate metal
drc["minwidth_metal2"] = 0.07
# METALINT.2 Minimum spacing of intermediate metal
drc["metal2_to_metal2"] = 0.07
# METALINT.3 Minimum enclosure around via1 on two opposite sides
drc["metal2_extend_via1"] = 0.035
# Reserved for asymmetric enclosures
drc["metal2_enclosure_via1"] = 0
# METALINT.4 Minimum enclosure around via[2-3] on two opposite sides
drc["metal2_extend_via2"] = 0.035
# Reserved for asymmetric enclosures
drc["metal2_enclosure_via2"] = 0
# Not a rule
drc["minarea_metal2"] = 0

# VIA2-3.1 Minimum width of Via[2-3]
drc["minwidth_via2"] = 0.065
# VIA2-3.2 Minimum spacing of Via[2-3]
drc["via2_to_via2"] = 0.075

# METALINT.1 Minimum width of intermediate metal
drc["minwidth_metal3"] = 0.07
# METALINT.2 Minimum spacing of intermediate metal
drc["metal3_to_metal3"] = 0.07
# METALINT.3 Minimum enclosure around via1 on two opposite sides
drc["metal3_extend_via2"] = 0.035
# Reserved for asymmetric enclosures
drc["metal3_enclosure_via2"] = 0
# METALINT.4 Minimum enclosure around via[2-3] on two opposite sides
drc["metal3_extend_via3"]=0.035
# Reserved for asymmetric enclosures
drc["metal3_enclosure_via3"] = 0
# Not a rule
drc["minarea_metal3"] = 0

# VIA2-3.1 Minimum width of Via[2-3]
drc["minwidth_via3"] = 0.065
# VIA2-3.2 Minimum spacing of Via[2-3]
drc["via3_to_via3"] = 0.075

# METALSMG.1 Minimum width of semi-global metal
drc["minwidth_metal4"] = 0.14
# METALSMG.2 Minimum spacing of semi-global metal
drc["metal4_to_metal4"] = 0.14
# METALSMG.3 Minimum enclosure around via[3-6] on two opposite sides
drc["metal4_extend_via3"] = 0.035
# Reserved for asymmetric enclosure
drc["metal4_enclosure_via3"] = 0.0025
# METALSMG.3 Minimum enclosure around via[3-6] on two opposite sides
drc["metal4_enclosure_via4"] = 0
# Reserved for asymmetric enclosure
drc["metal4_extend_via4"] = 0


drc["minwidth_via4"] = 0.14
drc["via4_to_via4"] = 0.14

drc["minwidth_metal5"] = 0.14
drc["metal5_to_metal5"] = 0.14
drc["metal5_extend_via4"] = 0.0025
drc["metal5_enclosure_via4"] = 0.0025
drc["metal5_enclosure_via5"] = 0.0025
drc["metal5_extend_via5"] = 0.0025

drc["minwidth_via5"] = 0.14
drc["via5_to_via5"] = 0.14

drc["minwidth_metal6"] = 0.14
drc["metal6_to_metal6"] = 0.14
drc["metal6_extend_via5"] = 0.0025
drc["metal6_enclosure_via5"] = 0.0025
drc["metal6_enclosure_via6"] = 0.0025
drc["metal6_extend_via6"] = 0.0025

drc["minwidth_via6"] = 0.14
drc["via6_to_via6"] = 0.14

drc["minwidth_metal7"] = 0.4
drc["metal7_to_metal7"] = 0.4
drc["metal7_extend_via6"] = 0.0025
drc["metal7_enclosure_via6"] = 0.0025
drc["metal7_enclosure_via7"] = 0.0025
drc["metal7_extend_via7"] = 0.0025

drc["minwidth_via7"] = 0.4
drc["via7_to_via7"] = 0.44

drc["minwidth_metal8"] = 0.4
drc["metal8_to_metal8"] = 0.4
drc["metal8_extend_via7"] = 0.0025
drc["metal8_enclosure_via7"] = 0.0025
drc["metal8_enclosure_via8"] = 0.0025
drc["metal8_extend_via8"] = 0.0025

drc["minwidth_via8"] = 0.4
drc["via8_to_via8"] = 0.44

drc["minwidth_metal9"] = 0.8
drc["metal9_to_metal9"] = 0.8
drc["metal9_extend_via8"] = 0.0025
drc["metal9_enclosure_via8"] = 0.0025
drc["metal9_enclosure_via9"] = 0.0025
drc["metal9_extend_via9"] = 0.0025

drc["minwidth_via9"] = 0.8
drc["via9_to_via9"] = 0.88

drc["minwidth_metal10"] = 0.8
drc["metal10_to_metal10"] = 0.8
drc["metal10_extend_via9"] = 0.0025
drc["metal10_enclosure_via9"] = 0.0025

#TODO lookup table DRC spacing rules needed

drc["wide_line_space_metal1"] = 0.09
drc["wide_length_threshold_metal1"] = 0.3
drc["wide_width_threshold_metal1"] = 0.09

drc["wide_line_space_metal2"] = 0.27
drc["wide_length_threshold_metal2"] = 0.27
drc["wide_width_threshold_metal2"] = 0.27

drc["line_end_threshold_metal3"] = 0.09
drc["line_end_line_space_metal3"] = 0.09

drc["wide_line_space_metal10"] = 1.5

# Metal 5-10 are ommitted

drc["rail_height"] = 0.135


###################################################
##END DRC/LVS Rules
###################################################

###################################################
##Spice Simulation Parameters
###################################################

#spice info
spice = {}
spice["gmin"] = 1e-13
spice["nmos"] = "nmos_vtg"
spice["pmos"] = "pmos_vtg"
# This is a map of corners to model files
SPICE_MODEL_DIR=os.environ.get("SPICE_MODEL_DIR")
spice["fet_models"] = { "TT" : [SPICE_MODEL_DIR+"/models_nom/PMOS_VTG.inc",SPICE_MODEL_DIR+"/models_nom/NMOS_VTG.inc"],
                        "FF" : [SPICE_MODEL_DIR+"/models_ff/PMOS_VTG.inc",SPICE_MODEL_DIR+"/models_ff/NMOS_VTG.inc"],
                        "SF" : [SPICE_MODEL_DIR+"/models_ss/PMOS_VTG.inc",SPICE_MODEL_DIR+"/models_ff/NMOS_VTG.inc"],
                        "FS" : [SPICE_MODEL_DIR+"/models_ff/PMOS_VTG.inc",SPICE_MODEL_DIR+"/models_ss/NMOS_VTG.inc"],
                        "SS" : [SPICE_MODEL_DIR+"/models_ss/PMOS_VTG.inc",SPICE_MODEL_DIR+"/models_ss/NMOS_VTG.inc"]}

#spice stimulus related variables
spice["feasible_period"] = 5         # estimated feasible period in ns
spice["supply_voltages"] = [0.9, 1.0, 1.1] # Supply voltage corners in [Volts]
spice["nom_supply_voltage"] = 1.0    # Nominal supply voltage in [Volts]
spice["rise_time"] = 0.005           # rise time in [Nano-seconds]
spice["fall_time"] = 0.005           # fall time in [Nano-seconds]
spice["temperatures"] = [0, 25, 100] # Temperature corners (celcius)
spice["nom_temperature"] = 25        # Nominal temperature (celcius)
spice["tx_instance_prefix"] = "m"


#sram signal names
#FIXME: We don't use these everywhere...
spice["vdd_name"] = "vdd"
spice["gnd_name"] = "gnd"
spice["control_signals"] = ["CSb", "WEb", "OEb"]
spice["data_name"] = "DATA"
spice["addr_name"] = "ADDR"
spice["minwidth_tx"] = drc["minwidth_tx"]
spice["channel"] = drc["minlength_channel"]
spice["clk"] = "clk"

# analytical delay parameters
spice["wire_unit_r"] = 0.38     # Unit wire resistance in ohms/square
spice["wire_unit_c"] = 0.15      # Unit wire capacitance ff/um^2
spice["min_tx_r"] = 9000       # Minimum transistor on resistance in ohms
spice["min_tx_drain_c"] = 0.18    # Minimum transistor drain capacitance in ff
spice["min_tx_gate_c"] = 0.12     # Minimum transistor gate capacitance in ff
spice["pmos_unit_gm"] = 68e-6
spice["nmos_unit_gm"] = 105e-6
spice["msflop_setup"] = 9        # DFF setup time in ps
spice["msflop_hold"] = 1         # DFF hold time in ps
spice["msflop_delay"] = 20.5     # DFF Clk-to-q delay in ps
spice["msflop_slew"] = 13.1      # DFF output slew in ps w/ no load
spice["msflop_in_cap"] = 0.2091  # Input capacitance of ms_flop (Din) [Femto-farad]
spice["dff_setup"] = 9        # DFF setup time in ps
spice["dff_hold"] = 1         # DFF hold time in ps
spice["dff_delay"] = 20.5     # DFF Clk-to-q delay in ps
spice["dff_slew"] = 13.1      # DFF output slew in ps w/ no load
spice["dff_in_cap"] = 0.2091  # Input capacitance of ms_flop (Din) [Femto-farad]

# analytical power parameters, many values are temporary
spice["bitcell_leakage"] = 1     # Leakage power of a single bitcell in nW
spice["inv_leakage"] = 1         # Leakage power of inverter in nW
spice["nand2_leakage"] = 1       # Leakage power of 2-input nand in nW
spice["nand3_leakage"] = 1       # Leakage power of 3-input nand in nW
spice["nor2_leakage"] = 1        # Leakage power of 2-input nor in nW
spice["msflop_leakage"] = 1      # Leakage power of flop in nW
spice["flop_para_cap"] = 2       # Parasitic Output capacitance in fF

spice["default_event_rate"] = 100           # Default event activity of every gate. MHz
spice["flop_transisition_prob"] = .5        # Transition probability of inverter.
spice["inv_transisition_prob"] = .5         # Transition probability of inverter.
spice["nand2_transisition_prob"] = .1875    # Transition probability of 2-input nand.
spice["nand3_transisition_prob"] = .1094    # Transition probability of 3-input nand.
spice["nor2_transisition_prob"] = .1875     # Transition probability of 2-input nor.

###################################################
##END Spice Simulation Parameters
###################################################

