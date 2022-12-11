from abc import ABC

from modules.push_rules.dual_bitcell_aligned_array import dual_bitcell_aligned_array


class single_mod_dual_bitcell_aligned_array(dual_bitcell_aligned_array, ABC):
    """
    Base class for arrays that are aligned with the bitcell array in groups of 2 using groups of 1 mods
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
        col_index = (mod_index - mod_index % 2) * self.words_per_row + mod_index % 2
        return self.bitcell_offsets[col_index]

    def create_layout(self):
        self.word_size *= 2
        super().create_layout()
        self.word_size = int(self.word_size / 2)

    def add_dummies(self):
        pass
