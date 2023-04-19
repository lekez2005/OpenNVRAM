setup_time = 0.15  # in nanoseconds
tech_name = "sky130"
process_corners = ["TT"]
supply_voltages = [1.8]
temperatures = [25]

diode = "diode.Diode"

logic_buffers_height = 3.9

control_buffers_num_rows = 1

# selected based on level shifter design
# which requires nmos height < inverter gain pin to prevent hvntm.2
level_shifter_nmos_width = 1.3
level_shifter_pmos_width = 0.42

# technology
analytical_delay = False
spice_name = "spectre"
tran_options = " errpreset=moderate "

# characterization parameters
default_char_period = 4e-9
enhance_pgate_pins = True

flat_lvs = True
flat_drc = True

default_drc_enable = 1

klayout_drc_options = {
    "feol": 1,
    "beol": default_drc_enable,
    "offgrid": default_drc_enable,
    "seal": default_drc_enable,
    "floating_met": 0
}

klayout_report_name = "report"


def configure_char_timing(options, class_name):
    if class_name == "FO4DelayCharacterizer":
        return 800e-12
    return default_char_period
