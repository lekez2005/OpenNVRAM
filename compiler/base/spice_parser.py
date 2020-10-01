"""
Implements a simple spice parser to enable constructing cell hierarchy
"""
import os
import re
from copy import deepcopy
from typing import Union, TextIO, List

SUFFIXES = {
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15
}


def tx_extract_parameter(param_name, statement):
    pattern = r"{}\s*=\s*(?P<value>[0-9e\.\-]+)(?P<suffix>[munpf]?)".format(param_name)
    match = re.search(pattern, statement)
    if not match:
        return None
    value = float(match.groups()[0])
    if match.groups()[1]:
        value *= SUFFIXES[match.groups()[1]]
    return value


def load_source(source: Union[str, TextIO]):
    if isinstance(source, str):
        if "\n" not in source and os.path.exists(source):
            with open(source, "r") as f:
                source = f.read()
    else:
        source.seek(0)
        source = source.read()
    return source


def extract_lines(source: str):
    all_lines = []
    for line in source.splitlines():
        if not line or not line.strip() or line.strip().startswith("*"):
            continue
        line = line.strip().lower()
        if '*' not in line:
            all_lines.append(line)
        else:  # strip comment from end if applicable

            end_index = len(line)
            for i in range(len(line)):
                if line[i] == "*" and end_index <= len(line):
                    end_index = min(i, end_index)
                elif line[i] in ["'", '"']:  # to prevent removing expressions
                    end_index = len(line)
            all_lines.append(line[:end_index].strip())

    return all_lines


MODE_INIT = 0
MODE_PARSING = 1
MODE_END = 2


def group_lines_by_mod(all_lines: List[str]):
    line_counter = 0

    lines_by_module = []

    mode = MODE_INIT

    current_mod = []

    while line_counter < len(all_lines):
        # construct a full line
        line = all_lines[line_counter]
        line_counter += 1
        while line_counter < len(all_lines):
            if all_lines[line_counter].startswith("+"):
                line += all_lines[line_counter][1:]
                line_counter += 1
            else:
                break

        if line.startswith(".subckt"):
            if len(current_mod) > 0:
                lines_by_module.append(current_mod)
            current_mod = [line]
            mode = MODE_PARSING
            continue
        elif line.startswith(".ends"):
            mode = MODE_END
            continue
        if mode == MODE_PARSING:
            current_mod.append(line)

    if len(current_mod) > 0:
        lines_by_module.append(current_mod)

    return lines_by_module  # List[List[str]]


class SpiceMod:
    def __init__(self, name: str, pins: List[str], contents: List[str]):
        self.name = name
        self.pins = pins
        self.contents = contents
        self.sub_modules = []  # type: List[SpiceMod]


class SpiceParser:

    def __init__(self, source: Union[str, TextIO]):
        self.mods = []  # type: List[SpiceMod]

        source = load_source(source)
        all_lines = extract_lines(source)

        mods_by_lines = group_lines_by_mod(all_lines)
        for mod_lines in mods_by_lines:
            subckt_line = mod_lines[0].split()
            mod_name = subckt_line[1]
            mod_pins = subckt_line[2:]
            self.mods.append(SpiceMod(mod_name, mod_pins,
                                      contents=[] if len(mod_lines) == 1 else mod_lines[1:]))

    def get_module(self, module_name):
        module_name = module_name.lower()
        for mod in self.mods:
            if mod.name == module_name:
                return mod
        assert False, module_name + " not in spice deck"

    def get_pins(self, module_name):
        return self.get_module(module_name).pins

    def deduce_hierarchy_for_pin(self, pin_name, module_name):
        module = self.get_module(module_name)
        hierarchy = []
        nested_hierarchy = []
        # breadth first and then go deep in each
        for line in module.contents:
            if pin_name not in line.split():
                continue

            pin_index = line.split().index(pin_name) - 1

            if not line.startswith("x"):  # end of hierarchy
                pin_index = line.split().index(pin_name) - 1
                hierarchy.append([(["d", "g", "s", "b"][pin_index], line)])
            else:
                child_module_name = line.split()[-1]
                child_module = self.get_module(child_module_name)
                child_pin_name = child_module.pins[pin_index]
                instance_name = line.split()[0]

                nested_hierarchy.append((instance_name, child_module_name, child_pin_name))

        # Now go deep into each branch
        for branch in nested_hierarchy:
            instance_name, child_module_name, child_pin_name = branch
            branch_hierarchy = self.deduce_hierarchy_for_pin(child_pin_name, child_module_name)
            for child in branch_hierarchy:
                hierarchy.append([instance_name] + child)

        return hierarchy

    def extract_caps_for_pin(self, pin_name, module_name):
        """
        Return caps attached to pin.
        Assumes transistor model name starts with n for nmos and p for pmos
        Note: Doesn't consider transistor length
        :param pin_name:
        :param module_name:
        :return: dict for each of nmos, pmos for gate/drain with list: [total, [(m, nf, w)]]
        """

        hierarchy = self.deduce_hierarchy_for_pin(pin_name, module_name)
        results = {
            "n": {
                "d": [0, []],
                "g": [0, []]
            },
            "p": {
                "d": [0, []],
                "g": [0, []]
            }
        }
        for child in hierarchy:
            spice_statement = child[-1][1]
            if not spice_statement.startswith("m"):
                continue
            line_elements = spice_statement.split()
            tx_type = line_elements[5][0]
            m = tx_extract_parameter("m", spice_statement) or 1
            nf = tx_extract_parameter("nf", spice_statement) or 1
            num_drains = 1 + int((nf - 1) / 2)
            width = tx_extract_parameter("w", spice_statement)

            pin_name = child[-1][0]
            pin_name = "d" if pin_name == "s" else pin_name

            results[tx_type][pin_name][0] += width * m * num_drains
            results[tx_type][pin_name][1].append((m, nf, width))

        return results
