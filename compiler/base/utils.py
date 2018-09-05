import imp
import math
import os
import subprocess
import time

import gdsMill
import globals
from pin_layout import pin_layout
import tech
from vector import vector


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
    number_grid = int(round(round((number / grid), 2), 0))
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




def auto_measure_libcell(pin_list, name, units, layer):
    """
    Open a GDS file and find the pins in pin_list as text on a given layer.
    Return these as a set of properties including the cell width/height too.
    """
    cell_gds = OPTS.openram_tech + "gds_lib/" + str(name) + ".gds"
    cell_vlsi = gdsMill.VlsiLayout(units=units)
    reader = gdsMill.Gds2reader(cell_vlsi)
    reader.loadFromFile(cell_gds)

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
    cell_gds = OPTS.openram_tech + "gds_lib/" + str(name) + ".gds"
    cell_vlsi = gdsMill.VlsiLayout(units=units)
    reader = gdsMill.Gds2reader(cell_vlsi)
    reader.loadFromFile(cell_gds)

    cell = {}
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
    cell_gds = OPTS.openram_tech + "gds_lib/" + str(name) + ".gds"
    cell_vlsi = gdsMill.VlsiLayout(units=units)
    reader = gdsMill.Gds2reader(cell_vlsi)
    reader.loadFromFile(cell_gds)

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


def run_command(command, stdout_file, stderror_file, verbose_level=1, cwd=None):

    verbose = OPTS.debug_level >= verbose_level
    if cwd is None:
        cwd = OPTS.openram_temp

    with open(stdout_file, "w") as stdout_f, open(stderror_file, "w") as stderr_f:
        stdout = subprocess.PIPE if verbose else stdout_f
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr_f, shell=True, cwd=cwd)
        while verbose:
            line = process.stdout.readline()
            if not line:
                break
            else:
                print line,
                stdout_f.write(line)

    if process is not None:
        while process.poll() is None:
            # Process hasn't exited yet, let's wait some
            time.sleep(0.5)
        return process.returncode
    else:
        return -1


def to_cadence(gds_file):
    to_cadence = imp.load_source("to_cadence",
                                 "/research/APSEL/ota2/openram/OpenRAM/technology/freepdk45/scripts/to_cadence.py")
    to_cadence.export_gds(gds_file)


