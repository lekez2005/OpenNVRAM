#! /usr/bin/env python3
"""
Extract layer capacitances and sheet resistances from calibre extraction rules file
Output may require post-processing
"""

import os
import re
import sys
from math import exp, pow
from pprint import pprint

scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts")
sys.path.append(scripts_dir)
sys.path.append(os.getenv("OPENRAM_HOME"))

tech_name = "freepdk45"
os.environ["OPENRAM_TECH_NAME"] = tech_name

from script_loader import load_setup

load_setup(top_level=True)
import tech

tech.layer_label_map = {}
from base.design import design

rcx_file = tech.drc["xrc_rules"]
output_file = os.path.join(os.path.dirname(__file__), "rc.txt")

all_layers = ["poly"] + ["metal{}".format(i + 1) for i in range(10)]
num_layers = len(all_layers)


def get_lines(obj_dict):
    with open(rcx_file, "r") as f:
        for line in f:
            yield line
            if len(obj_dict) == num_layers:
                break


def extract_single_line(prefix, pattern, obj_dict):
    for line in get_lines(obj_dict):
        if line.strip().startswith(prefix):
            match = pattern.search(line)
            if not match:
                print('Line "{}" does not match pattern "{}"'.format(line, pattern))
                sys.exit(-1)
            key, val = match.groups()

            if val.isnumeric:
                val = float(val)
            obj_dict[key] = val


def extract_multi_line_cap(pattern, obj_dict):
    within_definition = False
    within_content = False
    content = ""
    layer = ""
    for line in get_lines(obj_dict):
        line_stripped = line.strip()
        if pattern.search(line_stripped):
            within_definition = True
            content = ""
            within_content = False
            layer = pattern.search(line_stripped).groups()[0]
        if within_definition and line_stripped.startswith("C = "):
            within_content = True
        if within_content and line_stripped.startswith("]"):
            obj_dict[layer] = content.strip()
            within_content = within_definition = False
        if within_content:
            content += line


def extract_variable(var_name):
    d = {var_name: None}
    extract_single_line("VARIABLE {}".format(var_name),
                        re.compile(r"VARIABLE\s+({})\s+([\d\.]+)\s+".format(var_name)),
                        d)
    return d[var_name]


def extract_numbers(text):
    # return list(map(float, re.findall(r"(?<![a-zA-Z])([\d\.]+)[\)\s]* ", text)))
    return list(map(float, re.findall(r"[\(\-\s]+([\d\.]+)[\)\s]*", text)))


sheet_resistances = {}
intrinsic_plate = {}
intrinsic_fringe = {}
same_layer_caps = {}
thickness = {}
z_offset = {}

extract_single_line("PEX THICKNESS", re.compile(r"THICKNESS\s+(\S+).*(\s[\d\.]+)$"),
                    thickness)
extract_single_line("RESISTANCE SHEET", re.compile(r"RESISTANCE SHEET\s+(\S+)\s+\[([\d\.]+)\s+"),
                    sheet_resistances)

extract_single_line("metal", re.compile(r"^(metal[0-9]+)\s+([\d\.]+)\s+[\d\.]+"), z_offset)
extract_single_line("poly", re.compile(r"^(poly)\s+([\d\.]+)\s+[\d\.]+"), z_offset)

extract_multi_line_cap(re.compile(r"CAPACITANCE\s+INTRINSIC PLATE\s+(\S+)"),
                       intrinsic_plate)

extract_multi_line_cap(re.compile(r"CAPACITANCE\s+INTRINSIC FRINGE\s+(\S+)"),
                       intrinsic_fringe)
extract_multi_line_cap(re.compile(r"CAPACITANCE\s+NEARBODY\s+(\S+)\s+WITH\s+SHIELD\s+\1"),
                       same_layer_caps)

pprint(intrinsic_plate)
pprint(intrinsic_fringe)
pprint(same_layer_caps)

m34RS = extract_variable("m34RS")
m43nbk1 = extract_variable("m43nbk1")
m43nbk2 = extract_variable("m43nbk2")
m43nbk3 = extract_variable("m43nbk3")

m43ink1 = extract_variable("m43ink1")
m43ink2 = extract_variable("m43ink2")
m43ink3 = extract_variable("m43ink3")
m43ink4 = extract_variable("m43ink4")


def str_f(val):
    return "{:<8.3g}".format(val)


def calculate_cap(layer, width, space):
    adjacent_fringe = calculate_adjacent_fringe_cap(layer, width, space)
    ground_fringe = calculate_ground_fringe_cap(layer, width, space)
    intrinsic_cap = extract_numbers(intrinsic_plate[layer])[0]
    print("{:<10} \t\t{}\t\t{}\t\t{}".format(layer, *map(str_f,
                                          [adjacent_fringe, intrinsic_cap, ground_fringe])))
    return adjacent_fringe + intrinsic_cap + ground_fringe


def get_layer_radius(layer):
    radius_down = z_offset[layer]
    radius_up = radius_down + thickness[layer]
    return radius_down, radius_up


def calculate_adjacent_fringe_cap(layer, width, space):
    """Calculate fringe capacitance per unit area"""
    length = 1
    thick = thickness[layer]
    radius_down, radius_up = get_layer_radius(layer)
    # ignoring the m34RS since
    parameters = extract_numbers(same_layer_caps[layer])
    m1, m2, m3, m4, m5, m6, m7, m8, m9, m10 = parameters[:10]
    # ensure all numbers captured
    assert m6 == 2.0 and m9 == 2.0, "Parameters may be incorrect {}".format(parameters)
    total_cap = (
            length * (exp(-m1 - m2 * space) + m3 / (pow(space, m4))) *
            m5 * pow(width, m6) * (m7 * thick + m8) *
            (1 - m34RS * exp(-(m43nbk1 * radius_down + m43nbk2 * radius_up) / (m43nbk3 * space)))
    )
    return total_cap / width


def calculate_ground_fringe_cap(layer, width, space):
    """Calculate fringe capacitance to ground"""
    cap_def = intrinsic_fringe[layer]
    radius_down, radius_up = get_layer_radius(layer)
    # different nets so use same_net() == 0
    start_first_brace = cap_def.index("{")
    end_first_brace = cap_def.index("}")
    cap_def = cap_def[start_first_brace + 1: end_first_brace - 1].strip()
    parameters = extract_numbers(cap_def)
    m1, m2, m3, m4, m5, m6, m7, m8, m9, m10 = parameters
    # ensure all numbers captured
    assert m2 == 1.0 and m9 == 1.0, "Parameters may be incorrect {}".format(parameters)
    length = 1
    thick = thickness[layer]
    total_cap = (
            length * m1 * (1 - exp(-m3 * (space + m4))) *
            pow(width, m5 * space - m6) *
            (-m7 * thick + m8) *
            (1 - m34RS * exp(-(m43ink1 * radius_down + m43ink2 * radius_up) /
                             (m43ink3 * space + m43ink4 * m10)))
    )
    return total_cap / width


sample_design = design("dummy")

with open(output_file, "w") as f:
    for layer in ["poly"] + ["metal{}".format(i + 1) for i in range(10)]:
        min_width = sample_design.get_min_layer_width(layer)
        min_space = sample_design.get_space(layer)
        bus_width = sample_design.bus_width
        bus_space = sample_design.bus_space
        f.write("{} = [\n".format(layer))
        for width, space in zip([min_width, bus_width], [min_space, bus_space]):
            if width >= min_width and space >= min_space:
                cap = calculate_cap(layer, width, space)
                res = sheet_resistances[layer]
                f.write("    RC({}, {}, {}, {}),\n".format(*map(str_f, [width, space, res, cap])))
        f.write("]\n")
with open(output_file, "r") as f:
    print(f.read())
