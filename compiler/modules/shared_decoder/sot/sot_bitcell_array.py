from base.vector import vector
from globals import OPTS
from modules.shared_decoder.sotfet.sotfet_mram_bitcell_array import sotfet_mram_bitcell_array


class sot_bitcell_array(sotfet_mram_bitcell_array):
    @staticmethod
    def calculate_x_offsets(num_cols):
        x_offsets = sotfet_mram_bitcell_array.calculate_x_offsets(num_cols)
        # create space for reference cells
        bitcell, _, _ = sot_bitcell_array.create_modules()
        num_reference_cells = OPTS.num_reference_cells
        cell_grouping = OPTS.cells_per_group
        space = num_reference_cells * bitcell.width

        # TODO temp hack to prevent ref_write_driver clash
        res = sot_bitcell_array.insert_space_in_offsets(space, relative_offset=0.48,
                                                        all_offsets=x_offsets,
                                                        cell_grouping=cell_grouping)
        closest_offset, x_offsets = res
        OPTS.reference_cell_x = closest_offset
        return x_offsets

    def add_bitcell_cells(self):
        super().add_bitcell_cells()

        self.ref_cell = self.create_mod_from_str(OPTS.bitcell, mod_name=OPTS.ref_bitcell)

        reference_cell_x = OPTS.reference_cell_x
        cell_width = self.cell.width
        valid_offsets = [x for x in self.bitcell_offsets if x < reference_cell_x]
        start_col = len(valid_offsets)
        num_rows = self.row_size + 2 * OPTS.num_bitcell_dummies
        num_reference_cells = OPTS.num_reference_cells

        self.reference_insts = [[None] * num_rows for _ in range(num_reference_cells)]

        for i in range(num_reference_cells):
            col = start_col + i
            for row in range(num_rows):
                name = "ref_r{0}_c{1}".format(row, i)
                _, y_offset, mirror = self.get_cell_offset(col + OPTS.num_bitcell_dummies, row)
                x_offset = reference_cell_x + i * cell_width
                if "Y" in mirror:
                    x_offset += cell_width
                mod = self.cell if i % 2 == 0 else self.ref_cell
                cell_inst = self.add_inst(name=name, mod=mod,
                                          offset=vector(x_offset, y_offset),
                                          mirror=mirror)
                conns = self.get_bitcell_connections(row, col)
                bl_nets = "ref_bl[{0}] ref_br[{0}] ".format(i).split()
                conns[:2] = bl_nets
                self.connect_inst(conns)

                self.reference_insts[i][row] = cell_inst
                if row in self.dummy_rows:
                    self.horizontal_dummy[self.dummy_rows.index(row)] = cell_inst

    def add_pins(self):
        super().add_pins()
        for i in range(OPTS.num_reference_cells):
            self.add_pin_list("ref_bl[{0}] ref_br[{0}]".format(i).split())

    def add_layout_pins(self):
        super().add_layout_pins()
        for i, col_insts in enumerate(self.reference_insts):
            top_inst = col_insts[-1]
            bottom_inst = col_insts[0]
            for pin_name in ["bl", "br"]:
                pin = bottom_inst.get_pin(pin_name)
                self.add_layout_pin("ref_{}[{}]".format(pin_name, i), pin.layer,
                                    offset=pin.ll(), width=pin.width(),
                                    height=top_inst.get_pin(pin_name).uy() - pin.by())
