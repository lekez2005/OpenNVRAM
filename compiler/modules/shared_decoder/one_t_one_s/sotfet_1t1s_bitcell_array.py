from base.geometry import NO_MIRROR
from base.vector import vector
from globals import OPTS
from modules.shared_decoder.sotfet.sotfet_mram_bitcell_array import sotfet_mram_bitcell_array


class sotfet_1t1s_bitcell_array(sotfet_mram_bitcell_array):
    def add_body_tap_power_pins(self):
        pass

    def get_cell_offset(self, col_index, row_index):
        if self.bitcell_x_offsets is None:
            # calculate offsets
            _ = super().get_cell_offset(col_index, row_index)

        x_offset = self.combined_x_offsets[col_index]
        y_offset = self.combined_y_offsets[row_index]
        mirror = NO_MIRROR
        return x_offset, y_offset, mirror

    def add_body_taps(self):
        _, tap_offsets, _ = self.bitcell_x_offsets
        if hasattr(OPTS, "repeaters_array_space_offsets"):
            tap_offsets += OPTS.repeaters_array_space_offsets
        cell_offsets, _, dummy_offsets = self.bitcell_y_offsets
        sweep_var = range(self.row_size + 2 * OPTS.num_bitcell_dummies)

        cell_offsets = list(sorted(cell_offsets + dummy_offsets))

        for tap_offset in tap_offsets:
            for var in sweep_var:
                x_offset = tap_offset
                y_offset = cell_offsets[var]
                tap_inst = self.add_inst(name=self.body_tap.name, mod=self.body_tap,
                                         offset=vector(x_offset, y_offset), mirror=NO_MIRROR)
                self.connect_inst([])
                self.body_tap_insts.append(tap_inst)

