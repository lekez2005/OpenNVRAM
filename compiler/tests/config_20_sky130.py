from config_baseline import *

setup_time = 0.1  # in nanoseconds
tech_name = "sky130"
process_corners = ["TT"]
supply_voltages = [1.8]
temperatures = [25]

logic_buffers_height = 3.9

spice_name = "hspice"
lvs_extract_style = "extract style ngspice(si)"

# characterization parameters
default_char_period = 4e-9
enhance_pgate_pins = True


def configure_char_timing(options, class_name):
    if class_name == "FO4DelayCharacterizer":
        return 800e-12
    return default_char_period
