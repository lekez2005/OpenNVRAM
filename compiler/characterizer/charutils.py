import os
import re

import debug
from globals import OPTS


def relative_compare(value1, value2, error_tolerance=0.001):
    """ This is used to compare relative values for convergence. """
    return (abs(value1 - value2) / max(value1, value2) <= error_tolerance)


def get_measurement_file():
    if OPTS.spice_name == "xa":
        # customsim has a different output file name
        return "xa.meas"
    elif OPTS.spice_name == "spectre":
        if OPTS.use_ultrasim:
            return "stim.meas0"
        return "stim.measure"
    elif OPTS.spice_name in ["hspice", "Xyce"]:
        return "timing.mt0"
    else:
        # ngspice using a .lis file
        return "timing.lis"


def get_sim_file():
    if OPTS.spice_name == "spectre":
        return "tran.tran.tran"
    elif OPTS.spice_name == "hspice":
        return "timing.tr0"
    elif OPTS.spice_name in ["ngspice", "Xyce"]:
        return "timing.raw"
    elif OPTS.spice_name == "xa":
        return "xa"
    else:
        return "spice_stdout.log"


def parse_output(filename, key, find_max=True, sim_dir=None):
    """Parses a hspice output.lis file for a key value"""
    re_pattern = r"{0}\s*=\s*(-?\d+.?\d*[e]?[-+]?[0-9]*\S*)\s+.*".format(key)
    full_filename = get_measurement_file()
    if sim_dir:
        full_filename = os.path.join(sim_dir, full_filename)
    try:
        f = open(full_filename, "rt")
    except IOError:
        debug.error("Unable to open spice output file: {0}".format(full_filename), 1)
    else:
        with f:
            contents = f.read()
    # val = re.search(r"{0}\s*=\s*(-?\d+.?\d*\S*)\s+.*".format(key), contents)
    vals = re.findall(re_pattern, contents, flags=re.IGNORECASE)
    vals_float = list(map(convert_to_float, vals))
    if len(vals_float) == 0:
        return False
    elif len(vals_float) == 1:
        return vals_float[0]
    else:
        if find_max:
            if False in vals_float:
                return False
            else:
                return max(vals_float)
        else:
            return vals_float


def round_time(time, time_precision=3):
    # times are in ns, so this is how many digits of precision
    # 3 digits = 1ps
    # 4 digits = 0.1ps
    # etc.
    return round(time, time_precision)


def round_voltage(voltage, voltage_precision=5):
    # voltages are in volts
    # 3 digits = 1mv
    # 4 digits = 0.1mv
    # 5 digits = 0.01mv
    # 6 digits = 1uv
    # etc
    return round(voltage, voltage_precision)


def convert_to_float(number):
    """Converts a string into a (float) number; also converts units(m,u,n,p)"""
    if number == "Failed":
        return False

    # start out with a binary value
    float_value = False
    try:
        # checks if string is a float without letter units
        float_value = float(number)
    except ValueError:
        # see if it is in scientific notation
        unit = re.search(r"(-?\d+\.?\d*)e(\-?\+?\d+)", number)
        if unit != None:
            float_value = float(unit.group(1)) * (10 ^ float(unit.group(2)))

        # see if it is in spice notation
        unit = re.search(r"(-?\d+\.?\d*)(m?u?n?p?f?)", number)
        if unit != None:
            float_value = {
                'm': lambda x: x * 0.001,  # milli
                'u': lambda x: x * 0.000001,  # micro
                'n': lambda x: x * 0.000000001,  # nano
                'p': lambda x: x * 0.000000000001,  # pico
                'f': lambda x: x * 0.000000000000001  # femto
            }[unit.group(2)](float(unit.group(1)))

    # if we weren't able to convert it to a float then error out
    if not type(float_value) == float:
        debug.error("Invalid number: {0}".format(number), 1)
        return False

    return float_value


def vector_to_int(vec):
    return int("".join(map(str, vec)), 2)


def int_to_vec(int_, word_size):
    str_format = "0{}b".format(word_size)
    return list(map(int, [x for x in format(int_, str_format)]))
