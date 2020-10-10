import os
import re
import sys

import numpy as np

TEN_NINETY = "ten_ninety"
TEN_FIFTY_THRESH = "ten_fifty"


def parse_options(parser):
    first_arg = sys.argv[0]
    options, other_args = parser.parse_known_args()
    sys.argv = [first_arg] + other_args
    return options


def replace_arg(parser, arg_name, arg_type=float, default=None, choices=None):
    for action in parser._actions:
        if action.dest == arg_name:
            if choices is not None:
                action.choices = choices
            action.type = arg_type
            if default is not None:
                action.default = default
            return
    else:
        raise AssertionError('argument {} not found'.format(arg_name))


def search_meas(meas_name, meas_file_name):
    pattern = r"{}.*=\s+([0-9e\-\.]+)\s*$"
    with open(meas_file_name, "r") as meas_file:
        meas_content = meas_file.read()
        time = re.findall(pattern.format(meas_name), meas_content, re.MULTILINE)

    return time[0] if time else None


def get_scale_factor(method):
    if method == TEN_NINETY:
        scale_factor = np.log(0.9) - np.log(0.1)
    else:
        scale_factor = np.log(0.9) - np.log(0.5)
    return scale_factor


def get_measurement_threshold(method, vdd_value):
    if method == TEN_NINETY:
        rise_end = fall_start = 0.9 * vdd_value
        rise_start = fall_end = 0.1 * vdd_value
    else:
        rise_end = fall_end = 0.5 * vdd_value
        rise_start = 0.1 * vdd_value
        fall_start = 0.9 * vdd_value
    return rise_start, rise_end, fall_start, fall_end


def wrap_cell(cell, pin_name, wire_length_in: float, pin_dir=None,
              name_suffix=""):
    from base.design import design

    class CellWrapper(design):
        def __init__(self):

            if not wire_length_in:
                wire_length = 0
            else:
                wire_length = wire_length_in

            self.wire_length = wire_length
            self.original_dut = cell

            if wire_length == 0:
                pin_length_str = ""
            else:
                pin_length_str = "_pin_{}_l_{:.3g}".format(pin_name, wire_length)

            cell_name = "wrapped_{}{}{}".format(cell.name, pin_length_str, name_suffix)
            cell_name = cell_name.replace(".", "__")
            cell_name = cell_name.replace("[", "__").replace("]", "__")
            super().__init__(cell_name)

            pins = cell.pins

            self.add_mod(cell)
            cell_inst = self.add_inst(cell.name, cell, offset=[0, 0])
            self.connect_inst(pins)

            for pin in cell.pins:
                if not pin == pin_name:
                    self.copy_layout_pin(cell_inst, pin, pin)
                self.add_pin(pin)

            if wire_length == 0:
                self.copy_layout_pin(cell_inst, pin_name)
            else:
                pins = cell.get_pins(pin_name)
                for pin in pins:
                    if pin.width() >= pin.height() or pin_dir == "horz":  # left right
                        y_offset = pin.by()
                        if pin.lx() < 0.5 * cell.width:
                            x_offset = pin.lx() - wire_length
                        else:
                            x_offset = pin.rx()
                        pin_height = pin.height()
                        pin_width = wire_length
                    else:
                        x_offset = pin.lx()
                        if pin.by() < 0.5 * cell.height:
                            y_offset = pin.by() - wire_length
                        else:
                            y_offset = pin.uy()
                        pin_height = wire_length
                        pin_width = pin.width()
                    self.add_layout_pin(pin_name, pin.layer, offset=[x_offset, y_offset],
                                        width=pin_width, height=pin_height)

    return CellWrapper()


def files_by_beta(directory):
    # sort files by beta
    valid_files = []
    for f in os.listdir(directory):
        if f.startswith("beta_") and f.endswith(".json"):
            valid_files.append(f)

    sorted_files = list(sorted(valid_files, key=lambda x: float(x[5:-5])))
    return [os.path.join(directory, x) for x in sorted_files]
