from config_bitline import *
from config_bitline import buffer_repeater_sizes as baseline_repeater_sizes
from config_baseline import bank_class, control_buffers_class

baseline = True

sense_amp_mod = "latched_sense_amp"
sense_amp_tap = "latched_sense_amp_tap"
sense_amp_array = "latched_sense_amp_array"

# schematic simulation's positive feedback loop may be hard to break
buffer_repeater_sizes = baseline_repeater_sizes + [
    ("tri_en", ["tri_en_bar", "tri_en"], [10, 10])
]
