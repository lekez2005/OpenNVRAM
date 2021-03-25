from base.design import design, PIMP, NIMP
from base.geometry import MIRROR_X_AXIS, NO_MIRROR
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from globals import OPTS
from modules.horizontal.wordline_buffer import wordline_buffer
from modules.horizontal.wordline_pgate_tap import wordline_pgate_tap
from modules.push_rules.push_bitcell_array import push_bitcell_array


class wordline_buffer_array(design):
    rotation_for_drc = GDS_ROT_270

    def __init__(self, rows, buffer_stages):
        super().__init__("wordline_buffer_array")
        self.rows = rows
        self.buffer_stages = buffer_stages
        self.buffer_insts = []
        self.add_pins()
        self.create_layout()
        self.add_layout_pins()
        self.add_boundary()

    def add_pins(self):
        self.add_pin_list(["decode[{}]".format(x) for x in range(self.rows)])
        self.add_pin_list(["wl[{}]".format(x) for x in range(self.rows)])
        self.add_pin_list(["vdd", "gnd"])

    def create_layout(self):
        self.create_modules()
        self.add_modules()
        reference_mod = self.buffer.buffer_invs[0]
        reference_mod.create_dummies(self, top_y=self.buffer_insts[-1].by(),
                                     bottom_y=self.buffer_insts[0].by(),
                                     reference_mod=reference_mod)

    def create_modules(self):
        self.buffer = wordline_buffer(buffer_stages=self.buffer_stages, route_outputs=False)
        self.add_mod(self.buffer)

        self.pwell_tap = wordline_pgate_tap(self.buffer.buffer_invs[-1], PIMP)
        self.nwell_tap = wordline_pgate_tap(self.buffer.buffer_invs[-1], NIMP)

        bitcell = self.create_mod_from_str(OPTS.bitcell)
        body_tap = self.create_mod_from_str(OPTS.body_tap)

        self.bitcell_offsets, self.tap_offsets, _ = push_bitcell_array. \
            get_bitcell_offsets(self.rows, 2, bitcell, body_tap)

        self.width = self.buffer.width
        self.height = self.bitcell_offsets[-1] + 2 * self.buffer.height

    def add_modules(self):

        for i in range(self.rows):
            y_offset = self.bitcell_offsets[i]
            if i % 2 == 0:
                mirror = MIRROR_X_AXIS
                y_offset += self.buffer.height
            else:
                mirror = NO_MIRROR

            offset = vector(0, y_offset)
            buffer_inst = self.add_inst("driver{}".format(i), self.buffer, offset=offset,
                                        mirror=mirror)
            if len(self.buffer_stages) % 2 == 0:
                out_name, out_bar_name = "wl", "wl_bar"
            else:
                out_name, out_bar_name = "wl", "wl_bar"
            self.connect_inst(["decode[{}]".format(i), "{}[{}]".format(out_name, i),
                               "{}[{}]".format(out_bar_name, i), "vdd", "gnd"])
            self.buffer_insts.append(buffer_inst)
        self.tap_insts = []

        for y_offset in self.tap_offsets:
            tap_insts = wordline_pgate_tap.add_buffer_taps(self, 0, y_offset,
                                                           self.buffer.module_insts,
                                                           self.pwell_tap, self.nwell_tap)
            self.tap_insts.extend(tap_insts)

    def add_layout_pins(self):
        for pin_name in ["vdd", "gnd"]:
            for i in range(self.rows):
                self.copy_layout_pin(self.buffer_insts[i], pin_name)
        out_name = "out" if len(self.buffer_stages) % 2 == 0 else "out_inv"
        for i in range(self.rows):
            self.copy_layout_pin(self.buffer_insts[i], "in", "decode[{}]".format(i))
            self.copy_layout_pin(self.buffer_insts[i], out_name, "wl[{}]".format(i))
