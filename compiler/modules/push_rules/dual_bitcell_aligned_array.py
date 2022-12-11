import re
from abc import ABC
from typing import List

import debug
from base.design import design
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from globals import OPTS


class dual_bitcell_aligned_array(design, ABC):
    """
    Base class for arrays that are aligned with the bitcell array in groups of 2
    """

    vertical_pins = []  # type: List[str]
    horizontal_pins = []  # type: List[str]
    mod_rotation = GDS_ROT_270  # initial rotation of child module
    rotation_for_drc = GDS_ROT_270  # rotation of full for DRC runs
    mirror = True  # Mirror instances
    num_bitcell_dummies = 1
    instance_name_prefix = "child_mod_"

    @property
    def name(self):
        raise NotImplementedError

    @property
    def bus_pins(self) -> List[str]:
        raise NotImplementedError

    @property
    def mod_name(self) -> str:
        raise NotImplementedError

    def add_pins(self):
        raise NotImplementedError

    def __init__(self, columns=None, words_per_row=None, word_size=None, cols=None,
                 *args, **kwargs):
        name = self.__class__.name
        design.__init__(self, name)
        debug.info(1, "Creating {0}".format(self.name))
        if cols is not None:
            columns = cols
        if words_per_row is not None and word_size is not None:
            columns = word_size * words_per_row
        if word_size is not None:
            words_per_row = int(columns / word_size)

        self.word_size = int(columns / words_per_row)
        self.words_per_row = words_per_row
        self.columns = columns

        self.add_pins()
        self.create_modules()
        self.create_connection_template()
        self.create_layout()
        self.add_layout_pins()
        self.add_dummies()
        self.add_boundary()

    def create_modules(self):
        self.child_mod = self.create_mod_from_str(self.mod_name,
                                                  rotation=self.mod_rotation)

    def create_connection_template(self):
        mod_pins = self.child_mod.pins
        template = []
        for pin in mod_pins:
            pin_template = pin
            for bus_pin in self.bus_pins:
                if pin in [bus_pin + "<0>", bus_pin + "[0]"]:
                    pin_template = bus_pin + "[{0}]"
                    break
                elif pin in [bus_pin + "<1>", bus_pin + "[1]"]:
                    pin_template = bus_pin + "[{1}]"
                    break
            template.append(pin_template)
        self.connection_template = " ".join(template)

    def connect_mod(self, mod_index):
        word_index = mod_index * 2
        if self.mirror and mod_index % 2 == 1:
            i, next_i = word_index + 1, word_index
        else:
            i, next_i = word_index, word_index + 1
        self.connect_inst(self.connection_template.format(i, next_i).split())

    def create_layout(self):

        self.child_insts = []

        bitcell_array_cls = self.import_mod_class_from_str(OPTS.bitcell_array)
        offsets = bitcell_array_cls.calculate_x_offsets(num_cols=self.columns)

        (self.bitcell_offsets, self.tap_offsets, self.dummy_offsets) = offsets

        for i in range(int(self.word_size / 2)):
            x_offset = self.get_x_offset(i)
            name = self.instance_name_prefix + "{}".format(i)
            if self.mirror and i % 2 == 1:
                placement_x = x_offset + self.child_mod.width
                mirror = "MY"
            else:
                placement_x = x_offset
                mirror = ""
            child_inst = self.add_inst(name, self.child_mod, offset=vector(placement_x, 0),
                                       mirror=mirror)
            self.child_insts.append(child_inst)
            self.connect_mod(i)

        bitcell = self.create_mod_from_str(OPTS.bitcell)
        self.width = max(self.bitcell_offsets + self.dummy_offsets) + bitcell.width
        self.height = self.child_mod.height

    def get_x_offset(self, mod_index):
        bit = mod_index * 2
        col_index = bit * self.words_per_row
        return self.bitcell_offsets[col_index]

    def add_layout_pins(self):
        bus_pins = []

        for prefix in self.bus_pins:
            found = False
            regex_pattern = r"{}[\[\<].*".format(prefix)
            for pin_name in self.child_mod.pins:
                if re.match(regex_pattern, pin_name):
                    bus_pins.append(pin_name)
                    found = True
            if not found:
                bus_pins.append(prefix)

        for pin_name in self.child_mod.pins:
            if pin_name in self.horizontal_pins:
                for pin in self.child_insts[0].get_pins(pin_name):
                    self.add_layout_pin(pin_name, pin.layer, offset=vector(0, pin.by()),
                                        height=pin.height(), width=self.width)
            elif pin_name in bus_pins:
                for word_index in range(len(self.child_insts)):
                    conn_index = self.insts.index(self.child_insts[word_index])
                    pin_index = self.child_mod.pins.index(pin_name)
                    actual_connection = self.conns[conn_index][pin_index]
                    self.copy_layout_pin(self.child_insts[word_index], pin_name,
                                         actual_connection)
            else:
                self.copy_layout_pin(self.child_insts[0], pin_name)

    def add_dummies(self):
        pass
