from base.contact import cross_m1m2
from base.design import PIMP, NIMP, METAL1
from base.geometry import MIRROR_X_AXIS, NO_MIRROR
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from modules.bitcell_array import bitcell_array
from modules.horizontal.wordline_logic_buffer import WordlineLogicBuffer
from modules.horizontal.wordline_pgate_tap import wordline_pgate_tap
from modules.wordline_driver_array import wordline_driver_array


class wordline_buffer_array_horizontal(wordline_driver_array):
    rotation_for_drc = GDS_ROT_270

    def get_reference_mod(self):
        return self.logic_buffer.buffer_mod.buffer_invs[0]

    def create_buffer(self):
        self.logic_buffer = WordlineLogicBuffer(logic="pnand2", buffer_stages=self.buffer_stages,
                                                route_outputs=False)
        self.add_mod(self.logic_buffer)

    def create_modules(self):

        self.create_buffer()
        reference_mod = self.get_reference_mod()
        self.pwell_tap = wordline_pgate_tap(reference_mod, PIMP)
        self.nwell_tap = wordline_pgate_tap(reference_mod, NIMP)

        offsets = bitcell_array.calculate_y_offsets(num_rows=self.rows)
        self.bitcell_offsets, self.tap_offsets, _ = offsets

        self.width = self.logic_buffer.width
        self.height = self.bitcell_offsets[-1] + self.logic_buffer.height

    def get_row_y_offset(self, row):
        y_offset = self.bitcell_offsets[row]
        if row % 2 == 0:
            mirror = MIRROR_X_AXIS
            y_offset += self.logic_buffer.height
        else:
            mirror = NO_MIRROR

        return y_offset, mirror

    def route_en_pin(self, buffer_inst, en_pin):
        a_pin = buffer_inst.get_pin("A")
        self.add_cross_contact_center(cross_m1m2, vector(en_pin.cx(), a_pin.cy()), rotate=True)
        self.add_rect(METAL1, offset=vector(en_pin.cx(), a_pin.cy() - 0.5 * self.m1_width),
                      width=a_pin.lx() - en_pin.cx())

    def get_height(self):
        return self.bitcell_offsets[-1] + self.logic_buffer.height

    def add_modules(self):
        super().add_modules()

        reference_mod = self.get_reference_mod()
        reference_mod.create_dummies(self, top_y=self.buffer_insts[-1].by(),
                                     bottom_y=self.buffer_insts[0].by(),
                                     reference_mod=reference_mod)
        self.add_tap_insts()

    def add_tap_insts(self):

        # add taps
        self.tap_insts = []

        module_insts = [[self.logic_buffer.logic_inst],
                        self.logic_buffer.buffer_mod.module_insts[:1],
                        self.logic_buffer.buffer_mod.module_insts[1:]]
        x_offsets = [0, self.logic_buffer.buffer_inst.lx(), self.logic_buffer.buffer_inst.lx()]
        x_offsets = [x + self.buffer_insts[0].lx() for x in x_offsets]
        add_taps = [True, False, True]

        for y_offset in self.tap_offsets:
            for module_inst_list, x_offset, add_tap in zip(module_insts, x_offsets, add_taps):
                tap_insts = wordline_pgate_tap.add_buffer_taps(self, x_offset, y_offset,
                                                               module_inst_list,
                                                               self.pwell_tap, self.nwell_tap,
                                                               add_taps=add_tap)
                self.tap_insts.extend(tap_insts)
