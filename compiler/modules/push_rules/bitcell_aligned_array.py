from abc import ABC

from base.vector import vector
from modules.push_rules.dual_bitcell_aligned_array import dual_bitcell_aligned_array


class bitcell_aligned_array(dual_bitcell_aligned_array, ABC):
    """
    Base class for arrays that are aligned with the bitcell array in groups of 1
    """

    def create_connection_template(self):
        mod_pins = self.child_mod.pins
        template = []
        for pin in mod_pins:
            pin_template = pin
            if pin in self.bus_pins:
                pin_template = pin + "[{0}]"
            template.append(pin_template)
        self.connection_template = " ".join(template)

    def connect_mod(self, mod_index):
        self.connect_inst(self.connection_template.format(mod_index).split())

    def get_x_offset(self, mod_index):
        return (self.child_mod.width * self.num_dummies
                + (self.child_mod.width * self.words_per_row) * mod_index)

    def create_layout(self):
        self.word_size *= 2
        super().create_layout()
        self.word_size = int(self.word_size / 2)
        self.width = (self.columns + 2 * self.num_dummies) * self.child_mod.width

    def add_layout_pins(self):
        for pin_name in self.child_mod.pins:
            if pin_name in self.horizontal_pins:
                for pin in self.child_insts[0].get_pins(pin_name):
                    self.add_layout_pin(pin_name, pin.layer, offset=vector(0, pin.by()),
                                        height=pin.height(), width=self.width)
            elif pin_name in self.bus_pins:
                for word_index in range(len(self.child_insts)):
                    self.copy_layout_pin(self.child_insts[word_index], pin_name,
                                         "{}[{}]".format(pin_name, word_index))
            else:
                self.copy_layout_pin(self.child_insts[0], pin_name)

    def add_dummies(self):
        pass
