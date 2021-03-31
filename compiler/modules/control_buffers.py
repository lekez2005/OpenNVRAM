import collections
import itertools
from abc import ABC
from typing import List, Tuple, Union

import debug
from base import utils
from base.contact import m2m3, m1m2, cross_m2m3, cross_m1m2
from base.design import design, METAL3, METAL2, METAL1, DRAWING, ACTIVE
from base.geometry import NO_MIRROR, MIRROR_XY
from base.utils import round_to_grid as round_gd
from base.vector import vector
from base.well_implant_fills import get_default_fill_layers, create_wells_and_implants_fills
from globals import OPTS
from modules.buffer_stage import BufferStage
from modules.logic_buffer import LogicBuffer
from modules.horizontal.pgate_horizontal import pgate_horizontal
from pgates.pgate import pgate
from pgates.pinv import pinv
from pgates.pnand2 import pnand2
from pgates.pnand3 import pnand3
from pgates.pnor2 import pnor2

ModOffset = collections.namedtuple("ModOffset", "inst_name x_offset mirror")
Blockage = collections.namedtuple("Blockage", "x_offset top bottom")


class Rail:
    """Horizontal rails across modules"""

    def __init__(self, name, min_x, max_x):
        self.name = name
        self.index = -1
        self.min_x = min_x
        self.max_x = max_x
        self.rect = None

    def __repr__(self):
        return "Rail {}: min_x={:.3g} max_x={:.3g} index={}".format(self.name, self.min_x,
                                                                    self.max_x, self.index)


class SchemConnection:
    def __init__(self, inst_name: str, mod: design, connections: List[str]):
        self.inst_name = inst_name
        self.mod = mod
        self.connections = connections

    def __repr__(self):
        return "{}: {} {}".format(self.inst_name, self.mod.name, self.connections)


class PinConnection:
    """Instance/input pin index pairs"""
    DIRECT_VERT = "direct_vert"
    DIRECT_HORZ = "direct_horz"
    VERT = "vertical"

    def __init__(self, inst_name, net_name, pin_index, x_offset, conn_type,
                 prev_inst_name):
        self.inst_name = inst_name
        self.net_name = net_name
        self.pin_index = pin_index
        self.x_offset = x_offset
        self.conn_type = conn_type
        self.prev_inst_name = prev_inst_name

    def __repr__(self):
        return "{}:[{}|{}] -- {:.3g}".format(self.inst_name, self.pin_index, self.net_name,
                                             self.x_offset)


class ControlBuffers(design, ABC):
    name = "control_buffers"

    def __init__(self, contact_nwell=True, contact_pwell=True):
        design.__init__(self, self.name)
        debug.info(2, "Create Logic Buffers gate")

        self.logic_heights = OPTS.logic_buffers_height
        self.contact_pwell = contact_pwell
        self.contact_nwell = contact_nwell

        self.num_rows = OPTS.control_buffers_num_rows
        self.m2_blockages = []
        debug.check(self.num_rows in [1, 2], "Only one or two rows supported")

        self.create_layout()

    def create_schematic_connections(self) -> List[Tuple[str, design, List[str]]]:
        """e.g. [
        (inst_name, inv, ["a", "b", "out", "vdd", "gnd"
        ]
        """
        raise NotImplementedError

    @staticmethod
    def replace_connection(inst_name, new_connection, existing_connections):
        for i in range(len(existing_connections)):
            if existing_connections[i][0] == inst_name:
                existing_connections[i] = (inst_name, existing_connections[i][1],
                                           new_connection)
                break

    def get_schematic_pins(self) -> Tuple[List[str], List[str]]:
        """Tuple of ([input_pins], [output_pins])"""
        raise NotImplementedError

    def create_modules(self):
        raise NotImplementedError

    def create_layout(self):
        self.add_pins()
        self.create_modules()
        self.create_connections_mapping()
        self.create_schematic_connections()
        self.derive_module_offsets()

        self.derive_input_nets()
        self.create_pin_connections()

        self.derive_rails()
        self.add_rails()
        self.add_modules()

        self.evaluate_vertical_connection_types()

        self.route_pin_connections()
        self.add_output_pins()
        self.add_power_pins()
        self.fill_layers()
        self.add_boundary()

    def add_pins(self):
        """Add schematic pins"""
        self.input_pins, self.output_pins = self.get_schematic_pins()
        self.add_pin_list(self.input_pins + self.output_pins)
        self.add_pin_list(["vdd", "gnd"])

    def create_connections_mapping(self):
        schematic_connections = self.create_schematic_connections()

        self.schematic_connections = [SchemConnection(*x) for x in schematic_connections]
        self.connections_dict = {connection.inst_name: connection
                                 for connection in self.schematic_connections}

    def get_class_args(self, mod_class):
        args = {
            'height': self.logic_heights,
            'contact_nwell': self.contact_nwell,
            'contact_pwell': self.contact_pwell,
        }
        if issubclass(mod_class, (BufferStage, LogicBuffer)):
            args["route_outputs"] = False
        if issubclass(mod_class, LogicBuffer):
            args["route_inputs"] = False
        return args

    def create_mod(self, mod_class, **kwargs):
        buffer_stages_key = None
        if "buffer_stages" in kwargs:
            if isinstance(kwargs["buffer_stages"], str):
                buffer_stages_key = kwargs["buffer_stages"]
                kwargs["buffer_stages"] = getattr(OPTS, kwargs["buffer_stages"])
        args = self.get_class_args(mod_class)
        args.update(kwargs)
        mod = mod_class(**args)
        self.add_mod(mod)
        if buffer_stages_key is not None:
            mod.buffer_stages_str = buffer_stages_key
        return mod

    def create_common_modules(self):
        self.nand = self.create_mod(pnand2)
        self.nand_x2 = self.create_mod(pnand2, size=2)
        self.nand3 = self.create_mod(pnand3, size=1)
        self.nor = self.create_mod(pnor2)
        self.inv = self.create_mod(pinv)

    def create_clk_buf(self):
        self.clk_buf = self.create_mod(LogicBuffer, buffer_stages="clk_buffers",
                                       logic="pnand2")

    def create_wordline_en(self):
        assert len(OPTS.wordline_en_buffers) % 2 == 0, "Number of wordline buffers should be even"
        self.wordline_buf = self.create_mod(LogicBuffer,
                                            buffer_stages="wordline_en_buffers",
                                            logic="pnor2")

    def create_write_buf(self):
        self.write_buf = self.create_mod(LogicBuffer, buffer_stages="write_buffers",
                                         logic="pnor2")

    def create_precharge_buffers(self):
        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        self.precharge_buf = self.create_mod(LogicBuffer, buffer_stages="precharge_buffers",
                                             logic="pnand2")

    def create_sense_amp_buf(self):
        assert len(OPTS.sense_amp_buffers) % 2 == 1, "Number of sense_en buffers should be odd"
        self.sense_amp_buf = self.create_mod(LogicBuffer, buffer_stages="sense_amp_buffers",
                                             logic="pnand3")

    def create_tri_en_buf(self):
        self.tri_en_buf = self.create_mod(LogicBuffer, buffer_stages="tri_en_buffers",
                                          logic="pnand3")

    def create_sample_bar(self):
        assert len(OPTS.sampleb_buffers) % 2 == 0, "Number of sampleb buffers should be even"
        self.sample_bar = self.create_mod(BufferStage, buffer_stages="sampleb_buffers")

    def derive_module_offsets(self):
        if self.num_rows == 1:
            self.derive_single_row_offsets()
        else:
            self.derive_double_row_offsets()

        self.top_modules_offsets = list(sorted(filter(lambda x: x.mirror == NO_MIRROR,
                                                      self.module_offsets.values()),
                                               key=lambda x: x.x_offset))
        self.bottom_modules_offsets = list(sorted(filter(lambda x: x.mirror == MIRROR_XY,
                                                         self.module_offsets.values()),
                                                  key=lambda x: x.x_offset, reverse=True))

    def get_module_spacing(self, inst_name):
        sample_mod_offset = ModOffset(inst_name, 0, NO_MIRROR)

        module_connection = self.connections_dict[inst_name]
        input_nets, _ = self.get_module_connections(module_connection)
        if len(input_nets) >= 2:
            pin_index = 1
        else:
            pin_index = 0

        a_pin_offset = self.evaluate_pin_x_offset(sample_mod_offset, pin_index=pin_index)
        z_pin_allowance = self.inv.width - (self.inv.get_pin("Z").cx() + 0.5 * self.m2_width)
        space = -a_pin_offset + self.get_parallel_space(METAL2) - z_pin_allowance
        return utils.ceil(max(space, 0))

    def derive_single_row_offsets(self):
        """Get x offsets and mirrors for single row"""
        self.module_offsets = {}
        x_offset = 0
        for schem_conn in self.schematic_connections:
            inst_name, mod = schem_conn.inst_name, schem_conn.mod
            x_offset += self.get_module_spacing(inst_name)
            self.module_offsets[inst_name] = ModOffset(inst_name, x_offset, NO_MIRROR)
            x_offset += mod.width
        self.width = x_offset

    def derive_double_row_offsets(self):
        """Get x offsets and mirrors for double rows"""
        self.module_groups = self.evaluate_module_groups()
        self.group_split_index = self.calculate_split_index()
        self.module_offsets = {}
        x_offset = 0
        for module_group in self.module_groups[:self.group_split_index]:
            for inst_name in module_group:
                x_offset += self.get_module_spacing(inst_name)
                mod = self.connections_dict[inst_name].mod
                self.module_offsets[inst_name] = ModOffset(inst_name, x_offset, NO_MIRROR)
                x_offset += mod.width

        # calculate bottom width
        bottom_width = 0
        for module_group in self.module_groups[self.group_split_index:]:
            for inst_name in module_group:
                mod = self.connections_dict[inst_name].mod
                bottom_width += self.get_module_spacing(inst_name) + mod.width
        self.width = max(x_offset, bottom_width)
        x_offset = self.width

        for module_group in self.module_groups[self.group_split_index:]:
            for inst_name in module_group:
                mod = self.connections_dict[inst_name].mod
                x_offset -= self.get_module_spacing(inst_name)
                self.module_offsets[inst_name] = ModOffset(inst_name, x_offset, MIRROR_XY)
                x_offset -= mod.width
        return self.module_offsets

    def get_module_connections(self, connection: Union[SchemConnection, str]):
        """Separate module connections into inputs and outputs given inst_name"""
        if isinstance(connection, SchemConnection):
            inst_name = connection.inst_name
        else:
            inst_name = connection
        schem_conn = self.connections_dict[inst_name]
        mod = schem_conn.mod
        connections = schem_conn.connections
        if isinstance(mod, (pgate, pgate_horizontal)):
            return connections[:-1], connections[-1:]
        else:
            return connections[:-2], connections[-2:]

    def evaluate_module_groups(self, scramble=True):
        """Group modules together such that modules whose outputs
            connect directly to adjacent module inputs are not separated"""
        module_groups = [[self.schematic_connections[0].inst_name]]
        for i in range(len(self.schematic_connections) - 1):
            _, previous_outputs = self.get_module_connections(self.schematic_connections[i])
            current_inputs, _ = self.get_module_connections(self.schematic_connections[i + 1])
            inst_name = self.schematic_connections[i + 1].inst_name
            if set(current_inputs).intersection(previous_outputs):
                module_groups[-1].append(inst_name)
            else:
                module_groups.append([inst_name])

        # re-order such that for example (0 above 1), (2 above 3) and not (0 next to 1)
        if scramble:
            module_groups = (module_groups[:len(module_groups):2] +
                             list(reversed(module_groups[1:len(module_groups):2])))
        return module_groups

    def calculate_split_index(self):
        """Calculate index to split module_groups to "equalize" total widths of top and bottom modules"""
        module_groups = self.module_groups

        def group_width(group):
            return sum([self.connections_dict[x].mod.width for x in group])

        group_widths = list(map(group_width, module_groups))
        split_widths = []
        for i in range(1, len(module_groups) - 1):
            width = max(sum(group_widths[:i]), sum(group_widths[i:]))
            split_widths.append(width)
        self.width = min(split_widths)
        group_split_index = split_widths.index(min(split_widths))
        return group_split_index + 1

    def derive_input_nets(self):
        """Get nets that are connected to at least one module input
                and that aren't direct connections from adjacent modules"""
        input_connections = set(self.input_pins)
        for module_offsets in [self.top_modules_offsets, self.bottom_modules_offsets]:
            for i in range(len(module_offsets)):
                module_offset = module_offsets[i]
                module_connection = self.connections_dict[module_offset.inst_name]
                input_nets, _ = self.get_module_connections(module_connection)
                if i == 0:
                    input_connections.update(input_nets)
                else:
                    # remove adjacent direct connections
                    previous_offset = module_offsets[i - 1]
                    previous_connection = self.connections_dict[previous_offset.inst_name]
                    _, output_nets = self.get_module_connections(previous_connection)
                    difference = set(input_nets).difference(output_nets)
                    input_connections.update(difference)
        self.input_nets = input_connections

    def evaluate_pin_x_offset(self, module_offset: ModOffset, pin_index):
        """Evaluate x offset for an instance, pin_index combo"""
        inst_name = module_offset.inst_name
        inst_mod = self.connections_dict[inst_name].mod
        pin_name = inst_mod.pins[pin_index]
        pin = inst_mod.get_pin(pin_name)
        net_name = self.connections_dict[inst_name].connections[pin_index]
        _, output_nets = self.get_module_connections(inst_name)

        is_output = net_name in output_nets
        is_top_mod = module_offset.mirror == NO_MIRROR

        if is_output:
            x_offset = pin.cx() - 0.5 * self.m2_width
        elif pin_index == 0:
            if isinstance(inst_mod, pinv) or pin_name == "in":
                x_offset = pin.lx() - m1m2.height
            else:
                x_offset = pin.rx() - m1m2.height
        elif pin_index == 1:  # B pin
            a_pin = inst_mod.get_pin("A")
            x_space = self.get_parallel_space(METAL2) + self.m2_width
            x_offset = a_pin.rx() - m1m2.height - x_space
        elif pin_index == 2:  # C pin
            b_pin = inst_mod.get_pin("B")
            x_offset = b_pin.cx() - 0.5 * self.m2_width
        else:
            raise ValueError("Invalid pin index: {}".format(pin_index))

        if is_top_mod:
            x_offset += module_offset.x_offset
        else:
            x_offset = module_offset.x_offset - x_offset - self.m2_width
        return x_offset

    def find_non_blocked_m2(self, desired_x, blockage_top=None, blockage_bottom=None):
        """Find un-obstructed M2 x offset, and if the connection is direct"""
        desired_x = utils.round_to_grid(desired_x)

        all_m2_blockages = list(sorted(self.m2_blockages, reverse=True, key=lambda x: x.x_offset))
        all_m2 = list(map(lambda x: x.x_offset, all_m2_blockages))

        parallel_space = self.get_parallel_space(METAL2)  # space for parallel lines
        m2_pitch = parallel_space + self.m2_width

        y_space = self.get_line_end_space(METAL2)

        if all_m2 and desired_x >= max(all_m2) + m2_pitch:
            return desired_x, True

        # search left
        direct = True
        for index, x_offset in enumerate(all_m2):
            # first check for y overlap
            if blockage_top is not None and blockage_top + y_space < all_m2_blockages[index].bottom:
                continue
            elif blockage_bottom is not None and blockage_bottom - y_space > all_m2_blockages[index].top:
                continue
            # then check for x overlaps
            if x_offset - desired_x >= m2_pitch:
                # too far away on the right
                continue
            elif (x_offset >= desired_x and
                  utils.round_to_grid(x_offset - desired_x) < m2_pitch):  # to the right but too close
                desired_x = x_offset - m2_pitch
                direct = False
                continue
            elif (desired_x >= x_offset and
                  utils.round_to_grid(desired_x - x_offset) < m2_pitch):  # to the left but too close
                desired_x = x_offset - m2_pitch
                direct = False
                continue
            else:  # nothing close enough
                continue
        return desired_x, direct

    def create_pin_connections(self):
        """Evaluate all connections for module inputs/outputs and determine their x offsets"""

        def sort_func(x):
            return x.x_offset

        self.pin_connections = []  # type: List[PinConnection]

        all_module_offsets = [list(sorted(self.top_modules_offsets, key=sort_func)),
                              list(sorted(self.bottom_modules_offsets, key=sort_func, reverse=True))]

        for j in range(2):
            module_offsets = all_module_offsets[j]
            for i in range(len(module_offsets)):
                module_offset = module_offsets[i]
                input_nets, output_nets = self.get_module_connections(module_offset.inst_name)

                if len(input_nets) == 2:  # B pin is routed first
                    all_nets = list(reversed(input_nets))
                elif len(input_nets) == 3:
                    all_nets = [input_nets[1], input_nets[0], input_nets[2]]
                else:
                    all_nets = input_nets

                output_rail = set(output_nets).intersection(self.input_nets)
                if output_rail:
                    all_nets = all_nets + list(output_rail)
                if i > 0:
                    prev_inst_name = module_offsets[i - 1].inst_name
                    _, previous_outputs = self.get_module_connections(prev_inst_name)
                else:
                    prev_inst_name = None
                    previous_outputs = []
                for net in all_nets:
                    pin_index = self.connections_dict[module_offset.inst_name].connections.index(net)
                    kwargs = {"inst_name": module_offset.inst_name, "pin_index": pin_index,
                              "x_offset": None, "net_name": net,
                              "prev_inst_name": prev_inst_name}

                    if net in previous_outputs:
                        kwargs["conn_type"] = PinConnection.DIRECT_HORZ
                    else:
                        x_offset = self.evaluate_pin_x_offset(module_offset, pin_index)
                        if j == 1:
                            new_x, is_direct = self.find_non_blocked_m2(x_offset)
                            # actual x will be calculated after rails placement
                            x_offset = max(x_offset, new_x)

                        else:
                            is_direct = True
                        kwargs["x_offset"] = x_offset
                        kwargs["conn_type"] = (PinConnection.DIRECT_VERT
                                               if is_direct else PinConnection.VERT)
                        self.m2_blockages.append(Blockage(utils.round_to_grid(x_offset), None, None))
                    input_connection = PinConnection(**kwargs)
                    self.pin_connections.append(input_connection)

    def evaluate_vertical_connection_types(self):
        """Re-evaluate x offset and whether direct vertical connection for each connection
        Now that we know the rails y_offsets, some previously indirect connections can become direct if no y overlap
        """
        self.m2_blockages.clear()
        for pin_connection in self.pin_connections:
            if pin_connection.conn_type == PinConnection.DIRECT_HORZ:
                continue
            module_offset = self.module_offsets[pin_connection.inst_name]
            inst = self.inst_dict[pin_connection.inst_name]
            pin = inst.get_pin(inst.mod.pins[pin_connection.pin_index])
            rail = self.rails[pin_connection.net_name].rect

            is_top_mod = inst.by() > rail.cy()

            pin_index = pin_connection.pin_index
            x_offset = self.evaluate_pin_x_offset(module_offset, pin_index)

            if is_top_mod:
                is_direct = True
                blockage_top = pin.cy()
                blockage_bottom = rail.cy() - 0.5 * cross_m2m3.height
            else:
                blockage_top = rail.cy() + 0.5 * cross_m2m3.height
                blockage_bottom = pin.cy()
                x_offset, is_direct = self.find_non_blocked_m2(x_offset, blockage_top, blockage_bottom)

            pin_connection.x_offset = x_offset
            pin_connection.conn_type = PinConnection.DIRECT_VERT if is_direct else PinConnection.VERT

            self.m2_blockages.append(Blockage(utils.round_to_grid(x_offset), blockage_top, blockage_bottom))

    def derive_rail_max_min_offsets(self, input_nets):
        """Get min and max x offsets for rails"""
        self.rails = {}

        _, min_m3_width = self.calculate_min_area_fill(self.bus_width, layer=METAL3)

        # derive min and max x offsets based on center of source/destination pins
        for net in input_nets:
            if net in self.input_pins:
                min_x = 0
            else:
                min_x = self.width
            max_x = 0
            for input_connection in self.pin_connections:
                if not input_connection.net_name == net:
                    continue
                if input_connection.conn_type == PinConnection.DIRECT_HORZ:
                    continue

                x_offset = input_connection.x_offset
                min_x = min(min_x, x_offset + 0.5 * self.m2_width)
                max_x = max(max_x, x_offset + 0.5 * self.m2_width)
            max_x = max(max_x, min_x + min_m3_width)

            self.rails[net] = Rail(net, min_x, max_x)

    @staticmethod
    def evaluate_no_overlap_rail_indices(rails):
        if not rails:
            return -1
        sorted_rails = list(sorted(rails, key=lambda x: (x.min_x, x.max_x)))
        space_allowance = (m2m3.second_layer_height +
                           ControlBuffers.get_line_end_space(METAL3))

        for rail in sorted_rails:
            rail.index = -1

        for i in range(len(sorted_rails)):
            rail = sorted_rails[i]
            max_index = max([x.index for x in sorted_rails])

            rail.index = max_index + 1

            for rail_index in range(max_index + 1):
                overlap = False
                for existing_rail in filter(lambda x: x.index == rail_index, sorted_rails[:i]):
                    no_overlap = (rail.max_x + space_allowance < existing_rail.min_x
                                  or rail.min_x - space_allowance > existing_rail.max_x)
                    if not no_overlap:
                        overlap = True
                        break
                if not overlap:
                    rail.index = rail_index
                    break

        max_index = max([x.index for x in sorted_rails])
        return max_index

    def derive_rails(self):
        """Derive number of rails, rail extents and y indices"""
        self.derive_rail_max_min_offsets(self.input_nets)
        max_index = self.evaluate_no_overlap_rail_indices(self.rails.values())
        self.num_rails = max_index + 1

    def add_rails(self):
        """Add horizontal rails including input pins"""
        bus_pitch = self.bus_width + self.bus_space
        if self.num_rows == 1:
            y_base = 0
        else:
            sample_module = self.schematic_connections[0].mod
            y_base = sample_module.height + 0.5 * sample_module.rail_height + self.bus_space

            additional_rail = False
            # find indirect connections
            indirect_connections = [x for x in self.pin_connections if x.conn_type == PinConnection.VERT]
            for _, group in itertools.groupby(indirect_connections, lambda x: x.inst_name):
                if len(list(group)) > 1:  # add additional rail space if 2 indirect connections for one inst
                    additional_rail = True
            if additional_rail:
                rail_pitch = self.get_line_end_space(METAL2) + cross_m2m3.first_layer_height
                y_base += rail_pitch  # to permit routing when there is m2 blockage for bottom module

        for rail in self.rails.values():
            x_offset = 0 if rail.min_x == 0 else rail.min_x - 0.5 * m2m3.second_layer_height
            rail_end = rail.max_x + 0.5 * m2m3.second_layer_height
            y_offset = y_base + (self.num_rails - rail.index - 1) * bus_pitch
            kwargs = {"layer": METAL3, "offset": vector(x_offset, y_offset),
                      "width": rail_end - x_offset, "height": self.bus_width}
            if rail.name in self.input_pins:
                rail.rect = self.add_layout_pin(rail.name, **kwargs)
            else:
                rail.rect = self.add_rect(**kwargs)

        self.max_rail_y = max(self.rails.values(), key=lambda x: x.rect.uy()).rect.uy()
        self.min_rail_y = min(self.rails.values(), key=lambda x: x.rect.by()).rect.by()

    def add_modules(self):
        """Add modules to layout"""
        self.inst_dict = {}

        # top modules
        top_rail = max(self.rails.values(), key=lambda x: x.rect.uy())
        y_offset = top_rail.rect.uy() + self.bus_space + 0.5 * self.rail_height
        for offset in self.top_modules_offsets:
            connection = self.connections_dict[offset.inst_name]
            mod = connection.mod
            inst = self.add_inst(offset.inst_name, mod=mod,
                                 offset=vector(offset.x_offset, y_offset),
                                 mirror=offset.mirror)
            self.connect_inst(connection.connections + ["vdd", "gnd"])
            self.inst_dict[offset.inst_name] = inst

        self.height = next(iter(self.inst_dict.values())).uy()
        # bottom modules
        for offset in self.bottom_modules_offsets:
            connection = self.connections_dict[offset.inst_name]
            mod = connection.mod
            inst = self.add_inst(offset.inst_name, mod=mod,
                                 offset=vector(offset.x_offset,
                                               connection.mod.height), mirror=offset.mirror)
            self.connect_inst(connection.connections + ["vdd", "gnd"])
            self.inst_dict[offset.inst_name] = inst
        if self.num_rows == 1:
            self.top_insts = list(self.inst_dict.values())
            self.bottom_insts = []
        else:
            self.top_insts = list(filter(lambda x: x.by() > 0.5 * self.height,
                                         self.inst_dict.values()))
            self.bottom_insts = list(filter(lambda x: x.by() < 0.5 * self.height,
                                            self.inst_dict.values()))

    def route_pin_connections(self):
        """Route all module input pins"""
        self.indirect_m3_connections = {}

        for pin_connection in self.pin_connections:
            if pin_connection.conn_type == PinConnection.DIRECT_HORZ:
                self.route_adjacent_nets(pin_connection)
            elif pin_connection.conn_type == PinConnection.DIRECT_VERT:
                rail = self.rails[pin_connection.net_name].rect
                close_connection = self.locate_close_connection(pin_connection.x_offset, rail)
                if close_connection:  # to avoid min via space issue
                    width = close_connection.x_offset - pin_connection.x_offset
                    if width > 0:
                        width += self.m2_width
                    self.add_rect(METAL2, offset=vector(pin_connection.x_offset,
                                                        rail.cy() - 0.5 * self.m2_width),
                                  width=width)
                    self.route_direct_rail_to_pin(pin_connection, rail, pin_connection.x_offset,
                                                  add_rail_via=False)
                else:
                    self.route_direct_rail_to_pin(pin_connection, rail, pin_connection.x_offset)
            else:
                self.route_indirect_rail_to_pin(pin_connection)

    def route_adjacent_nets(self, pin_connection: PinConnection):
        """Route nets for which there is a direct connection available
                from output Z pin to adjacent input"""
        input_inst = self.inst_dict[pin_connection.inst_name]
        output_inst = self.inst_dict[pin_connection.prev_inst_name]
        net = pin_connection.net_name

        in_pin_index = self.connections_dict[input_inst.name].connections.index(net)
        input_pin_name = input_inst.mod.pins[in_pin_index]

        output_connection = self.connections_dict[output_inst.name]
        out_pin_index = output_connection.connections.index(net)
        output_pin_name = output_inst.mod.pins[out_pin_index]
        if in_pin_index == 0:
            self.connect_z_to_outer_pin(out_inst=output_inst, in_inst=input_inst,
                                        out_name=output_pin_name, in_name=input_pin_name)
        else:
            self.connect_z_to_inner_pin(out_inst=output_inst, in_inst=input_inst,
                                        out_name=output_pin_name, in_name=input_pin_name)

    def connect_z_to_outer_pin(self, out_inst, in_inst, out_name="Z", in_name="A"):
        in_pin = in_inst.get_pin(in_name)
        out_pin = out_inst.get_pin(out_name)
        self.add_rect(METAL1, offset=vector(out_pin.rx(), in_pin.cy() - 0.5 * self.m1_width),
                      width=in_pin.lx() - out_pin.rx())

    def connect_z_to_inner_pin(self, out_inst, in_inst, out_name="Z", in_name="B"):
        in_pin = in_inst.get_pin(in_name)
        out_pin = out_inst.get_pin(out_name)
        x_offset = out_pin.cx() - 0.5 * self.m2_width

        if out_inst.mirror == NO_MIRROR:
            y_offset = in_pin.cy() - 0.5 * self.m2_width
            height = out_pin.uy() - y_offset
        else:
            y_offset = out_pin.by()
            height = in_pin.cy() + 0.5 * self.m2_width - y_offset

        self.add_rect(METAL2, offset=vector(x_offset, y_offset), height=height)

        self.add_rect(METAL2, offset=vector(x_offset, in_pin.cy() - 0.5 * self.m2_width),
                      width=in_pin.cx() - x_offset)
        self.add_contact_center(m1m2.layer_stack, offset=in_pin.center())

    def route_direct_rail_to_pin(self, pin_connection: PinConnection, rail, x_offset,
                                 add_rail_via=True):
        """Route from horizontal rails to instance pins"""
        net = pin_connection.net_name
        input_inst = self.inst_dict[pin_connection.inst_name]
        pin_index = self.connections_dict[input_inst.name].connections.index(net)
        pin_name = input_inst.mod.pins[pin_index]

        if pin_name in ["Z", "out", "out_inv"]:
            conn_func = self.connect_z_pin
        elif pin_index == 0:
            conn_func = self.connect_a_pin
        elif pin_index == 1:
            conn_func = self.connect_b_pin
        else:
            conn_func = self.connect_c_pin

        conn_func(input_inst, pin_name, rail, x_offset, add_rail_via)

    def locate_close_connection(self, x_offset, rail):
        via_space = self.get_via_space(m2m3)
        via_width = m2m3.contact_width
        x_offset = round_gd(x_offset)
        for pin_connection in self.pin_connections:
            if (pin_connection.conn_type == PinConnection.DIRECT_VERT and
                    rail.cy() == self.rails[pin_connection.net_name].rect.cy()):  # potential via on same net
                candidate_x_offset = round_gd(pin_connection.x_offset)
                if candidate_x_offset < x_offset <= \
                        round_gd(candidate_x_offset + via_width + via_space):
                    return pin_connection
                if x_offset < candidate_x_offset <= round_gd(x_offset + via_width + via_space):
                    return pin_connection
        return None

    def route_indirect_rail_to_pin(self, pin_connection: PinConnection):

        inst_name = pin_connection.inst_name
        net = pin_connection.net_name
        original_rail = self.rails[net].rect

        # evaluate M3 rail min_x and max_x
        pin_index = self.connections_dict[inst_name].connections.index(net)
        original_x_offset = self.evaluate_pin_x_offset(self.module_offsets[inst_name], pin_index)

        m3_x_offset = pin_connection.x_offset + 0.5 * self.m2_width - 0.5 * m2m3.height
        _, min_m3_width = self.calculate_min_area_fill(self.m3_width, layer=METAL3)
        m3_end_x = original_x_offset + max(0.5 * self.m2_width + 0.5 * m2m3.height, min_m3_width)
        m3_width = m3_end_x - m3_x_offset

        # find unoccupied m3 rail y offset
        rail_indices = list(sorted(self.indirect_m3_connections.keys()))
        if not rail_indices:
            min_rail_y = min(self.min_rail_y + 0.5 * self.bus_width - 0.5 * m2m3.contact_width -
                             self.get_space("via2") - m2m3.contact_width,
                             self.min_rail_y + 0.5 * self.bus_width - 0.5 * m2m3.height -  # to bottom via
                             self.get_line_end_space(METAL2) -  # to top via
                             0.5 * m2m3.height - 0.5 * self.m3_width)
            rail_y = min_rail_y
            rail_index = 0
        else:
            rail_pitch = self.get_line_end_space(METAL2) + cross_m2m3.first_layer_height
            rail_x_space = self.get_line_end_space(METAL3)
            rail_index = 0
            while True:
                if rail_index not in self.indirect_m3_connections:
                    # starting new rail index
                    rail_y = self.indirect_m3_connections[rail_index - 1][0][2] - rail_pitch
                    break
                # loop through existing rails
                existing_rails = self.indirect_m3_connections[rail_index]
                # look for clashes
                clash = False
                for min_x, max_x, _ in existing_rails:
                    if min_x - rail_x_space < m3_x_offset < max_x + rail_x_space:
                        clash = True
                        break
                    elif min_x - rail_x_space < m3_end_x < max_x + rail_x_space:
                        clash = True
                        break
                if clash:
                    rail_index += 1
                else:
                    rail_y = self.indirect_m3_connections[rail_index][0][2]
                    break
        if rail_index not in self.indirect_m3_connections:
            self.indirect_m3_connections[rail_index] = []
        self.indirect_m3_connections[rail_index].append((m3_x_offset, m3_end_x, rail_y))

        # add m2 to new rail
        _, min_m2_height = self.calculate_min_area_fill(self.m2_width, layer=METAL2)
        m2_height = max(min_m2_height, original_rail.cy() - rail_y)
        self.add_rect(METAL2, offset=vector(pin_connection.x_offset, rail_y), height=m2_height)
        via_x = pin_connection.x_offset + 0.5 * self.m2_width

        close_connection = self.locate_close_connection(pin_connection.x_offset, original_rail)
        if close_connection:  # to avoid min via space issue
            self.add_rect(METAL2, offset=vector(pin_connection.x_offset,
                                                original_rail.cy() - 0.5 * self.m2_width),
                          width=close_connection.x_offset - pin_connection.x_offset)
        else:
            self.add_cross_contact_center(cross_m2m3, offset=vector(via_x, original_rail.cy()),
                                          rotate=False)

        if via_x + 0.5 * m2m3.contact_width + self.get_via_space(m2m3) > original_x_offset:
            # use a direct M2 connection (no vias)
            new_rail = self.add_rect(METAL2, offset=vector(via_x, rail_y),
                                     width=original_x_offset + self.m2_width - via_x)
            self.route_direct_rail_to_pin(pin_connection, new_rail, original_x_offset,
                                          add_rail_via=False)
            return

        self.add_cross_contact_center(cross_m2m3,
                                      offset=vector(via_x, rail_y + 0.5 * self.m3_width),
                                      rotate=False)

        new_rail = self.add_rect(METAL3, offset=vector(m3_x_offset, rail_y), width=m3_width)

        self.route_direct_rail_to_pin(pin_connection, new_rail, original_x_offset)

    def join_rail_to_y_offset(self, x_offset, y_offset, rail, add_rail_via):
        if add_rail_via:
            via_x = x_offset + 0.5 * self.m2_width
            self.add_cross_contact_center(cross_m2m3, offset=vector(via_x, rail.cy()), rotate=False)
        if y_offset < rail.cy():
            y_offset -= 0.5 * self.m2_width
        self.add_rect(METAL2, offset=vector(x_offset, rail.cy()), height=y_offset - rail.cy())

    def connect_a_pin(self, inst, pin_name, rail, x_offset, add_rail_via):
        pin = inst.get_pin(pin_name)
        self.join_rail_to_y_offset(x_offset, pin.cy(), rail, add_rail_via)

        if pin.cy() > rail.cy():
            via_x = x_offset + m1m2.height
        else:
            via_x = x_offset + self.m2_width
        self.add_contact(m1m2.layer_stack, offset=vector(via_x,
                                                         pin.cy() - 0.5 * m1m2.width),
                         rotate=90)

    def connect_b_pin(self, inst, pin_name, rail, x_offset, add_rail_via):
        pin = inst.get_pin(pin_name)

        self.join_rail_to_y_offset(x_offset, pin.cy(), rail, add_rail_via)

        self.add_rect(METAL2, offset=vector(x_offset, pin.cy() - 0.5 * self.m2_width),
                      width=pin.cx() - x_offset)
        self.add_cross_contact_center(cross_m1m2, offset=pin.center(), rotate=False)

    def connect_c_pin(self, inst, pin_name, rail, x_offset, add_rail_via):
        pin = inst.get_pin(pin_name)
        a_pin = inst.get_pin("A")
        self.join_rail_to_y_offset(x_offset, a_pin.cy(), rail, add_rail_via)

        self.add_rect(METAL2, offset=vector(x_offset, a_pin.cy() - 0.5 * self.m2_width),
                      width=pin.cx() - x_offset)
        self.add_cross_contact_center(cross_m1m2, offset=vector(pin.cx(), a_pin.cy()),
                                      rotate=False)

    def connect_z_pin(self, inst, pin_name, rail, x_offset, add_rail_via):
        pin = inst.get_pin(pin_name)
        y_offset = pin.by() if pin.cy() > rail.cy() else pin.uy()
        self.join_rail_to_y_offset(x_offset, y_offset, rail, add_rail_via)

    def get_output_driver(self, pin_name):
        for connection in self.schematic_connections:
            _, output_nets = self.get_module_connections(connection)
            if pin_name in output_nets:
                mod_conns = connection.connections
                mod_pin_name = connection.mod.pins[mod_conns.index(pin_name)]
                mod_inst = self.inst_dict[connection.inst_name]
                out_pin = mod_inst.get_pin(mod_pin_name)
                return mod_inst, out_pin

    def add_output_pins(self):
        """Add layout output pins"""
        for pin_name in self.output_pins:
            mod_inst, out_pin = self.get_output_driver(pin_name)
            x_offset = out_pin.cx() - 0.5 * self.m2_width
            if out_pin.cy() > 0.5 * self.height:
                self.add_layout_pin(pin_name, METAL2,
                                    offset=vector(x_offset, out_pin.uy()),
                                    height=self.height - out_pin.uy())
            else:
                self.add_layout_pin(pin_name, METAL2, offset=vector(x_offset, 0),
                                    height=out_pin.by())

    def get_output_pin_names(self):
        _, output_pins = self.get_schematic_pins()
        return output_pins

    def get_input_pin_names(self):
        input_pins, _ = self.get_schematic_pins()
        return input_pins

    def add_power_pins(self):
        """Add vdd and gnd pins"""
        insts = self.top_insts[:1] + self.bottom_insts[:1]
        for pin_name in ["vdd", "gnd"]:
            for inst in insts:
                pin = inst.get_pin(pin_name)
                self.add_layout_pin(pin_name, pin.layer, offset=vector(0, pin.by()),
                                    height=pin.height(), width=self.width)

    def fill_layers(self):
        """Fill spaces between adjacent modules"""
        layers, purposes = get_default_fill_layers()
        layers.append(ACTIVE)
        purposes.append(DRAWING)

        instances = [self.top_insts[:-1], self.top_insts[1:]]
        if len(self.bottom_insts) > 1:
            bottom_insts = list(reversed(self.bottom_insts))
            instances[0].extend(bottom_insts[:-1])
            instances[1].extend(bottom_insts[1:])

        def get_edge_mod(inst, is_input):
            mod = inst.mod
            if isinstance(mod, pgate):
                edge_mod = mod
            elif isinstance(mod, BufferStage):
                if is_input:
                    edge_mod = mod.buffer_invs[0]
                else:
                    edge_mod = mod.buffer_invs[-1]
            elif isinstance(mod, LogicBuffer):
                if is_input:
                    edge_mod = mod.logic_mod
                else:
                    edge_mod = mod.buffer_mod.buffer_invs[-1]
            else:
                raise ValueError("Invalid instance mod {}".format(mod.name))
            return edge_mod

        for left_inst, right_inst in zip(instances[0], instances[1]):
            if left_inst.rx() >= right_inst.lx():
                continue
            if left_inst.mirror == NO_MIRROR:
                is_inputs = (False, True)
            else:
                is_inputs = (True, False)
            left_mod = get_edge_mod(left_inst, is_inputs[0])
            right_mod = get_edge_mod(right_inst, is_inputs[1])
            for fill_rect in create_wells_and_implants_fills(left_mod, right_mod,
                                                             layers, purposes):

                layer, _, _, left_rect, right_rect = fill_rect
                if (round_gd(left_rect.width) < round_gd(left_mod.width) or
                        round_gd(right_rect.width) < round_gd(right_mod.width)):
                    continue

                rect_bottom = round_gd(max(left_rect.by(), right_rect.by()))
                rect_top = round_gd(max(left_rect.uy(), right_rect.uy()))
                height = rect_top - rect_bottom
                if left_inst.mirror == MIRROR_XY:
                    rect_bottom = left_inst.height - rect_top

                self.add_rect(layer, offset=vector(left_inst.rx(), left_inst.by() + rect_bottom),
                              width=right_inst.lx() - left_inst.rx(),
                              height=height)
