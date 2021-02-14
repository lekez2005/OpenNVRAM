from base import utils
from base.contact import m1m2
from base.design import METAL2
from base.geometry import NO_MIRROR, MIRROR_XY
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from modules.baseline_latched_control_buffers import LatchedControlBuffers
from modules.buffer_stage import BufferStage
from modules.control_buffers import ModOffset
from modules.logic_buffer import LogicBuffer
from modules.push_rules.buffer_stages_horizontal import BufferStagesHorizontal
from modules.push_rules.logic_buffer_horizontal import LogicBufferHorizontal
from modules.push_rules.pgate_horizontal_tap import pgate_horizontal_tap
from modules.push_rules.pinv_horizontal import pinv_horizontal
from modules.push_rules.pnand2_horizontal import pnand2_horizontal
from modules.push_rules.pnor2_horizontal import pnor2_horizontal
from pgates.pinv import pinv
from pgates.pnand2 import pnand2
from pgates.pnor2 import pnor2
from tech import drc


class LatchedControlLogic(LatchedControlBuffers):
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

    def get_schematic_pins(self):
        pins = super().get_schematic_pins()
        if self.is_left_bank:
            pins[1].remove("wordline_en")
        pins[1].remove("write_en_bar")
        pins[1].remove("tri_en_bar")
        return pins

    def create_schematic_connections(self):
        connections = super().create_schematic_connections()
        if self.is_left_bank:
            self.replace_connection("wordline_buf", None, connections)
        connections = [x for x in connections if x[2] is not None]
        return connections

    def get_class_args(self, mod_class):
        return {}

    def create_mod(self, mod_class, **kwargs):
        class_map = {
            pnand2: pnand2_horizontal,
            pnor2: pnor2_horizontal,
            pinv: pinv_horizontal,
            LogicBuffer: LogicBufferHorizontal,
            BufferStage: BufferStagesHorizontal
        }
        mod_class = class_map.get(mod_class, mod_class)
        return super().create_mod(mod_class, **kwargs)

    def create_modules(self):
        super().create_modules()
        self.logic_heights = self.inv.height
        self.body_tap = self.create_mod(pgate_horizontal_tap, pgate_mod=self.inv)

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
        module_offsets, tap_offsets, width = self.create_module_group_offsets(
            module_groups)
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
