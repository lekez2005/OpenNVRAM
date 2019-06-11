import importlib.util
import math
import os
import subprocess
import time
from importlib import reload

import globals
import tech
from base.pin_layout import pin_layout
from base.vector import vector
from gdsMill import gdsMill

try:
    from tech import layer_pin_map
except ImportError:
    layer_pin_map = {}

OPTS = globals.OPTS

def ceil(decimal):
    """
    Performs a ceiling function on the decimal place specified by the DRC grid.
    """
    grid = tech.drc["grid"]
    return math.ceil(decimal * 1 / grid) / (1 / grid)

def round_to_grid(number):
    """
    Rounds an arbitrary number to the grid.
    """
    grid = tech.drc["grid"]  
    # this gets the nearest integer value
    # 0.001 added for edge cases: round(196.5, 0) rounds to 196 in python3 but 197 in python 2
    number_grid = int(math.copysign(1, number) * round(round((abs(number) / grid), 2) + 0.001, 0))
    number_off = number_grid * grid
    return number_off

def snap_to_grid(offset):
    """
    Changes the coodrinate to match the grid settings
    """
    return [round_to_grid(offset[0]),round_to_grid(offset[1])]

def pin_center(boundary):
    """
    This returns the center of a pin shape in the vlsiLayout border format.
    """
    return [0.5 * (boundary[0] + boundary[2]), 0.5 * (boundary[1] + boundary[3])]

def pin_rect(boundary):
    """
    This returns a LL,UR point pair.
    """
    return [vector(boundary[0],boundary[1]),vector(boundary[2],boundary[3])]


def transform(pos, offset, mirror, rotate):
    if mirror == "MX":
        pos = pos.scale(1, -1)
    elif mirror == "MY":
        pos = pos.scale(-1, 1)
    elif mirror == "XY":
        pos = pos.scale(-1, -1)

    if rotate == 90:
        pos = pos.rotate_scale(-1, 1)
    elif rotate == 180:
        pos = pos.scale(-1, -1)
    elif rotate == 270:
        pos = pos.rotate_scale(1, -1)

    return pos + offset


def transform_relative(pos, inst):
    return transform(pos, offset=inst.offset, mirror=inst.mirror, rotate=inst.rotate)


def get_pin_rect(pin, instances):
    first = pin.ll()
    second = pin.ur()
    for instance in reversed(instances):
        (first, second) = map(lambda x: transform_relative(x, instance), [first, second])
    ll = [min(first[0], second[0]), min(first[1], second[1])]
    ur = [max(first[0], second[0]), max(first[1], second[1])]
    return ll, ur


def get_tap_positions(num_columns):
    c = __import__(OPTS.bitcell)
    bitcell = getattr(c, OPTS.bitcell)

    if not OPTS.use_body_taps:
        bitcell_offsets = [i*bitcell.width for i in range(num_columns)]
        return bitcell_offsets, []

    from modules import body_tap as mod_body_tap

    body_tap = mod_body_tap.body_tap

    cells_spacing = int(math.ceil(0.9*tech.drc["latchup_spacing"]/bitcell.width))
    tap_width = body_tap.width
    i = 0
    tap_positions = []
    while i <= num_columns:
        tap_positions.append(i)
        i += cells_spacing
    if tap_positions[-1] == num_columns:
        tap_positions[-1] = num_columns - 1  # prevent clash with cells to the right of bitcell array
    if len(tap_positions) >= 3:
        tap_positions = [tap_positions[0]] + tap_positions[1:-1:2] + [tap_positions[-1]]
    tap_positions = list(sorted(set(tap_positions)))
    x_offset = 0.0
    positions_index = 0
    bitcell_offsets = [None]*num_columns
    tap_offsets = []
    for i in range(num_columns):
        if positions_index < len(tap_positions) and i == tap_positions[positions_index]:
            tap_offsets.append(x_offset)
            x_offset += tap_width
            positions_index += 1
        bitcell_offsets[i] = x_offset
        x_offset += bitcell.width
    return bitcell_offsets, tap_offsets


def get_body_tap_width():
    from modules.body_tap import body_tap
    return body_tap().width



def auto_measure_libcell(pin_list, name, units, layer):
    """
    Open a GDS file and find the pins in pin_list as text on a given layer.
    Return these as a set of properties including the cell width/height too.
    """
    cell_gds = os.path.join(OPTS.openram_tech, "gds_lib", str(name) + ".gds")
    cell_vlsi = gdsMill.VlsiLayout(units=units, from_file=cell_gds)
    cell_vlsi.load_from_file()

    cell = {}
    measure_result = cell_vlsi.getLayoutBorder(layer)
    if measure_result == None:
        measure_result = cell_vlsi.measureSize(name)
    [cell["width"], cell["height"]] = measure_result

    for pin in pin_list:
        (name,layer,boundary)=cell_vlsi.getPinShapeByLabel(str(pin))        
        cell[str(pin)] = pin_center(boundary)
    return cell



def get_libcell_size(name, units, layer):
    """
    Open a GDS file and return the library cell size from either the
    bounding box or a border layer.
    """
    cell_gds = os.path.join(OPTS.openram_tech, "gds_lib", str(name) + ".gds")
    cell_vlsi = gdsMill.VlsiLayout(units=units, from_file=cell_gds)
    cell_vlsi.load_from_file()

    measure_result = cell_vlsi.getLayoutBorder(layer)
    if measure_result == None:
        measure_result = cell_vlsi.measureSize(name)
    # returns width,height
    return measure_result


def get_libcell_pins(pin_list, name, units, layer):
    """
    Open a GDS file and find the pins in pin_list as text on a given layer.
    Return these as a rectangle layer pair for each pin.
    """
    cell_gds = os.path.join(OPTS.openram_tech, "gds_lib", str(name) + ".gds")
    cell_vlsi = gdsMill.VlsiLayout(units=units, from_file=cell_gds)
    cell_vlsi.load_from_file()

    cell = {}
    for pin in pin_list:
        cell[str(pin)]=[]
        label_list=cell_vlsi.getPinShapeByLabel(str(pin), layer_pin_map=layer_pin_map)
        for label in label_list:
            (name,layer,boundary)=label
            rect = pin_rect(boundary)
            # this is a list because other cells/designs may have must-connect pins
            cell[str(pin)].append(pin_layout(pin, rect, layer))
    return cell


def load_class(class_name):
    config_mod_name = getattr(OPTS, class_name)
    class_file = reload(__import__(config_mod_name))
    return getattr(class_file, config_mod_name)


def run_command(command, stdout_file, stderror_file, verbose_level=1, cwd=None):

    verbose = OPTS.debug_level >= verbose_level
    if cwd is None:
        cwd = OPTS.openram_temp
    with open(stdout_file, "w") as stdout_f, open(stderror_file, "w") as stderr_f:
        stdout = subprocess.PIPE if verbose else stdout_f
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr_f, shell=True, cwd=cwd)
        while verbose:
            line = process.stdout.readline().decode()
            if not line:
                process.stdout.close()
                break
            else:
                print(line, end=" ")
                stdout_f.write(line)

    if process is not None:
        while process.poll() is None:
            # Process hasn't exited yet, let's wait some
            time.sleep(0.5)
        return process.returncode
    else:
        return -1


def get_temp_file(file_name):
    return os.path.join(OPTS.openram_temp, file_name)


def to_cadence(gds_file):
    file_path = "/research/APSEL/ota2/openram/OpenRAM/technology/freepdk45/scripts/to_cadence.py"
    spec = importlib.util.spec_from_file_location("to_cadence", file_path)
    to_cadence = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(to_cadence)
    to_cadence.export_gds(gds_file)

