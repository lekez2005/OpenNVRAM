import math

import numpy as np

from base.design import METAL1, design
from base.library_import import library_import
from globals import OPTS
from tech import drc


@library_import
class sotfet_mram_bitcell(design):
    pin_names = ["BL", "BR", "RWL", "WWL"]
    lib_name = OPTS.mram_bitcell

    def calculate_array_offsets(self, num_rows):
        tap_height = self.rail_height + self.get_parallel_space(METAL1)

        # 0.9 for safety
        cells_spacing = int(math.ceil(0.9 * drc["latchup_spacing"] / self.height))

        tap_positions = (np.arange(cells_spacing / 2, num_rows, cells_spacing).
                         astype(np.int).tolist())

        tap_offsets = []
        bitcell_offsets = [None] * num_rows

        y_offset = 0.0
        tap_index = 0

        for i in range(num_rows):
            if tap_index < len(tap_positions) and i == tap_positions[tap_index]:
                # only add taps at even offsets
                if i % 2 == 0:
                    tap_offsets.append(y_offset)
                    y_offset += tap_height
                    bitcell_offsets[i] = y_offset
                    y_offset += self.height
                else:
                    bitcell_offsets[i] = y_offset
                    y_offset += self.height
                    tap_offsets.append(y_offset)
                    y_offset += tap_height
                tap_index += 1
            else:
                bitcell_offsets[i] = y_offset
                y_offset += self.height

        return bitcell_offsets, tap_offsets
