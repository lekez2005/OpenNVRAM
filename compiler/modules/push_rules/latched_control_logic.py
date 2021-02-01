from base import utils
from base.contact import m1m2
from base.design import METAL2
from base.geometry import NO_MIRROR, MIRROR_XY
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from globals import OPTS
from modules.control_buffers import ControlBuffers, ModOffset
from modules.push_rules.buffer_stages_horizontal import BufferStagesHorizontal
from modules.push_rules.logic_buffer_horizontal import LogicBufferHorizontal
from modules.push_rules.pgate_horizontal_tap import pgate_horizontal_tap
from modules.push_rules.pinv_horizontal import pinv_horizontal
from modules.push_rules.pnand2_horizontal import pnand2_horizontal
from modules.push_rules.pnor2_horizontal import pnor2_horizontal
from tech import drc


class LatchedControlLogic(ControlBuffers):
    """
    Generate and buffer control signals using bank_sel, clk and read, sense_trig and precharge_trig
    Assumes
    Inputs:
        bank_sel, read, clk, sense_trig, precharge_trig
    Define internal signal
        bank_sel_cbar = NAND(clk_bar, bank_sel)
    Outputs
        clk_buf:            bank_sel.clk
        wordline_en: and3((sense_trig_bar + read_bar), bank_sel, clk_bar)
                    = nor(bank_sel_cbar, nor(sense_trig_bar, read_bar))
                    = nor(bank_sel_cbar, and(sense_trig, read)) sense_trig = 0 during writes
                    =       nor(bank_sel_cbar, sense_trig)
        write_en:           and3(read_bar, clk_bar, bank_sel) = nor(read, bank_sel_cbar)
        precharge_en_bar: and2(bank_sel, precharge_trig)
        sampleb:    NAND4(bank_sel, sense_trig_bar, clk_bar, read)
                    = NAND2(AND(bank_sel.clk_bar, sense_trig_bar), read)
                    = NAND2(nor(bank_sel_cbar, sense_trig), read)
                    =       nand2( nor(bank_sel_cbar, sense_trig), read)
        sense_en: bank_sel.sense_trig (same as tri_en)
        tri_en_bar: sense_en_bar
    """
    rotation_for_drc = GDS_ROT_270

    def __init__(self, is_left_bank=False):
        self.is_left_bank = is_left_bank
        if is_left_bank:
            self.name += "_left"
        super().__init__()

    def get_schematic_pins(self):
        wordline = [] if self.is_left_bank else ["wordline_en"]
        return (
            ["bank_sel", "read", "clk", "sense_trig", "precharge_trig"],
            (["clk_buf", "clk_bar"] + wordline +
             ["precharge_en_bar", "write_en", "sense_en", "tri_en", "sample_bar"])
        )

    def create_modules(self):
        self.inv = pinv_horizontal(size=1)
        self.add_mod(self.inv)

        self.body_tap = pgate_horizontal_tap(self.inv)

        self.logic_heights = self.inv.height

        self.nand2 = pnand2_horizontal(size=1)
        self.add_mod(self.nand2)

        self.nor2 = pnor2_horizontal(size=1)
        self.add_mod(self.nor2)

        self.clk_buf = LogicBufferHorizontal(buffer_stages=OPTS.clk_buffers, logic="pnand2")
        self.add_mod(self.clk_buf)

        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        self.precharge_buf = LogicBufferHorizontal(OPTS.precharge_buffers, "pnand2")
        self.add_mod(self.precharge_buf)

        if not self.is_left_bank:
            assert len(OPTS.wordline_en_buffers) % 2 == 0, "Number of wordline buffers should be even"
            self.wordline_buf = LogicBufferHorizontal(OPTS.wordline_en_buffers, "pnor2")
            self.add_mod(self.wordline_buf)

        assert len(OPTS.write_buffers) % 2 == 0, "Number of write buffers should be even"
        self.write_buf = LogicBufferHorizontal(OPTS.write_buffers, "pnor2")
        self.add_mod(self.write_buf)

        assert len(OPTS.sampleb_buffers) % 2 == 0, "Number of sampleb buffers should be even"
        self.sample_bar = LogicBufferHorizontal(OPTS.sampleb_buffers, "pnand2")
        self.add_mod(self.sample_bar)

        assert len(OPTS.sense_amp_buffers) % 2 == 1, "Number of sense_en buffers should be odd"
        self.sense_amp_buf = BufferStagesHorizontal(OPTS.sense_amp_buffers)
        self.add_mod(self.sense_amp_buf)

        assert len(OPTS.tri_en_buffers) % 2 == 1, "Number of tri_en buffers should be odd"
        self.tri_en_buf = BufferStagesHorizontal(OPTS.tri_en_buffers)
        self.add_mod(self.tri_en_buf)

    def create_schematic_connections(self):
        connections = [
            ("clk_buf", self.clk_buf, ["bank_sel", "clk", "clk_bar", "clk_buf"]),
            ("precharge_buf", self.precharge_buf,
             ["bank_sel", "precharge_trig", "precharge_en_bar", "precharge_en"]),
            ("sel_trig", self.nand2, ["bank_sel", "sense_trig", "sel_trig_bar"]),
            ("clk_bar_int", self.inv, ["clk", "clk_bar_int"]),
            ("bank_sel_cbar_inst", self.nand2, ["bank_sel", "clk_bar_int", "bank_sel_cbar"])
        ]
        if not self.is_left_bank:
            connections.append(("wordline_buf", self.wordline_buf,
                                ["sense_trig", "bank_sel_cbar", "wordline_en", "wordline_en_bar"]))
        connections.extend([
            ("write_buf", self.write_buf, ["read", "bank_sel_cbar", "write_en", "write_en_bar"]),
            ("sel_cbar_trig", self.nor2, ["sense_trig", "bank_sel_cbar", "sel_cbar_trig"]),
            ("sample_bar", self.sample_bar,
             ["read", "sel_cbar_trig", "sample_bar", "sample_en_buf"]),
            ("sense_amp_buf", self.sense_amp_buf, ["sel_trig_bar", "sense_en", "sense_en_bar"]),
            ("tri_en_buf", self.tri_en_buf, ["sel_trig_bar", "tri_en", "tri_en_bar"]),
        ])
        return connections

    def get_module_spacing(self, _):
        return 0

    def get_body_tap_index(self, module_groups):
        """Find indices to insert body taps"""
        group_widths = list(map(
            lambda group: sum([self.connections_dict[x].mod.width for x in group]),
            module_groups))

        all_indices = []

        cell_spacing = utils.floor(0.9 * drc["latchup_spacing"])
        total_width = sum(group_widths)
        x_offset = min(total_width, cell_spacing)

        def index_sum(index):
            return sum(group_widths[:index + 1])

        while x_offset <= total_width:
            valid_indices = [i for i in range(len(group_widths)) if index_sum(i) < x_offset]
            closest_index = max(valid_indices)
            all_indices.append(closest_index + 1)
            x_offset += cell_spacing

        return all_indices

    def create_module_group_offsets(self, module_groups):
        tap_indices = self.get_body_tap_index(module_groups)
        module_offsets = {}
        tap_offsets = []
        x_offset = 0
        for i in range(len(module_groups)):
            if i in tap_indices:
                tap_offsets.append(x_offset)
                x_offset += self.body_tap.width
            module_group = module_groups[i]
            for inst_name in module_group:
                mod = self.connections_dict[inst_name].mod
                module_offsets[inst_name] = ModOffset(inst_name, x_offset, NO_MIRROR)
                x_offset += mod.width
        width = x_offset
        return module_offsets, tap_offsets, width

    def derive_single_row_offsets(self):
        self.module_offsets = {}
        module_groups = self.evaluate_module_groups(scramble=False)
        module_offsets, tap_offsets, width = self.create_module_group_offsets(module_groups)
        self.top_tap_offsets = tap_offsets
        self.module_offsets = module_offsets
        self.bottom_tap_offsets = []
        self.width = width

    def derive_double_row_offsets(self):
        self.module_groups = self.evaluate_module_groups(scramble=True)
        self.group_split_index = self.calculate_split_index()
        self.module_offsets = {}

        self.module_offsets, self.top_tap_offsets, top_width = \
            self.create_module_group_offsets(self.module_groups[:self.group_split_index])

        bottom_offsets, bottom_tap_offsets, bottom_width = \
            self.create_module_group_offsets(self.module_groups[self.group_split_index:])
        self.width = max(top_width, bottom_width)
        x_shift = self.width - bottom_width
        self.bottom_tap_offsets = [x + x_shift + self.body_tap.width for x in bottom_tap_offsets]
        for inst_name, offset in bottom_offsets.items():
            mod = self.connections_dict[inst_name].mod
            x_offset = offset.x_offset + x_shift + mod.width
            self.module_offsets[inst_name] = ModOffset(inst_name, x_offset, MIRROR_XY)

    def add_modules(self):
        """Add regular modules and bottom taps"""
        super().add_modules()
        top_inst = self.inst_dict[self.top_modules_offsets[0].inst_name]
        for x_offset in self.top_tap_offsets:
            self.add_inst(self.body_tap.name, self.body_tap,
                          offset=vector(x_offset, top_inst.by()))
            self.connect_inst([])

        if len(self.bottom_modules_offsets) > 0:
            bottom_inst = self.inst_dict[self.bottom_modules_offsets[0].inst_name]
            for x_offset in self.bottom_tap_offsets:
                self.add_inst(self.body_tap.name, self.body_tap,
                              offset=vector(x_offset, bottom_inst.uy()),
                              mirror=MIRROR_XY)
                self.connect_inst([])

    def evaluate_pin_x_offset(self, module_offset: ModOffset, pin_index):
        inst_name = module_offset.inst_name
        inst_mod = self.connections_dict[inst_name].mod
        pin_name = inst_mod.pins[pin_index]
        pin = inst_mod.get_pin(pin_name)
        is_top_mod = module_offset.mirror == NO_MIRROR

        x_offset = pin.cx() - 0.5 * self.m2_width

        if is_top_mod:
            x_offset += module_offset.x_offset
        else:
            x_offset = module_offset.x_offset - x_offset - self.m2_width
        return x_offset

    def connect_z_to_inner_pin(self, out_inst, in_inst, out_name="Z", in_name="B"):
        in_pin = in_inst.get_pin(in_name)
        out_pin = out_inst.get_pin(out_name)
        self.add_contact(m1m2.layer_stack,
                         offset=vector(out_pin.cx() - 0.5 * m1m2.first_layer_width,
                                       out_pin.cy() - 0.5 * m1m2.first_layer_height))
        self.add_rect(METAL2, offset=vector(out_pin.cx(), out_pin.cy() - 0.5 * self.m2_width),
                      width=in_pin.cx() - out_pin.cx())
        self.add_contact_center(m1m2.layer_stack, offset=vector(in_pin.cx(), out_pin.cy()))

    def make_straight_connection(self, inst, pin_name, rail, x_offset, add_rail_via):
        pin = inst.get_pin(pin_name)
        if pin.cy() > rail.cy():
            via_y = pin.by()
        else:
            via_y = pin.uy() - m1m2.height
        self.join_rail_to_y_offset(x_offset, via_y, rail, add_rail_via)
        self.add_contact(m1m2.layer_stack, offset=vector(x_offset, via_y))

    def connect_a_pin(self, inst, pin_name, rail, x_offset, add_rail_via):
        self.make_straight_connection(inst, pin_name, rail, x_offset, add_rail_via)

    def connect_z_pin(self, inst, pin_name, rail, x_offset, add_rail_via):
        self.make_straight_connection(inst, pin_name, rail, x_offset, add_rail_via)

    def connect_b_pin(self, inst, pin_name, rail, x_offset, add_rail_via):
        self.make_straight_connection(inst, pin_name, rail, x_offset, add_rail_via)

    def connect_c_pin(self, inst, pin_name, rail, x_offset, add_rail_via):
        self.make_straight_connection(inst, pin_name, rail, x_offset, add_rail_via)

    def fill_layers(self):
        pass

    def add_layout_pin(self, text, layer, offset, width=None, height=None):
        _, output_nets = self.get_schematic_pins()
        if text in output_nets:
            if self.num_rows == 2 and offset.y < 0.5 * self.height:
                via_y = offset.y + height
            else:
                via_y = offset.y - m1m2.height
            self.add_contact(m1m2.layer_stack, offset=vector(offset.x, via_y))
        return super().add_layout_pin(text, layer, offset, width, height)
