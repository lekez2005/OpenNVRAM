"""
Create Graph consisting of nodes from one driver to the next
TODO
    - More accurate gm evaluation, characterization or calculation
    - Handle case with multiple input pins in layout
    - More systematic pin length computation, currently uses max(pin_length, min(cell_width, cell_height))
    - Distributed loads are not detected if the nesting hierarchy is greater than one -> Implement flatenning load hierarchy to fix
"""

import math
from typing import List, Tuple, Dict, Union

import debug
from base.design import design
from base.hierarchy_spice import OUTPUT, INOUT, INPUT, delay_data


class GraphLoad:

    def __init__(self, pin_name: str, module: design, wire_length: float = 0.0, count: int = 1):
        self.pin_name = pin_name
        self.module = module
        self.count = count
        self.wire_length = wire_length
        self.cin = 0.0

    def is_distributed(self):
        from globals import OPTS
        if self.count >= OPTS.distributed_load_threshold:
            return True
        if self.module.is_delay_primitive():
            return False
        instances_groups = self.module.group_pin_instances_by_mod(self.pin_name)
        return instances_groups and max(map(lambda x: x[0],
                                            instances_groups.values())) > OPTS.distributed_load_threshold

    def increment(self):
        self.count += 1

    def evaluate_cin(self):
        self.cin, _ = self.module.get_input_cap(pin_name=self.pin_name, num_elements=self.count,
                                                wire_length=self.wire_length)
        return self.cin

    def __str__(self):
        if self.cin > 0:
            suffix = " c={:.3g}f".format(self.cin * 1e15)
        else:
            suffix = ""
        return "({}:{} count={}{})".format(self.module.name, self.pin_name, self.count, suffix)


class GraphLoads:

    def __init__(self):
        self.loads = {}  # type: Dict[str, GraphLoad]

    def add_load(self, pin_name: str, module: design, wire_length: float = 0.0,
                 count: int = 1, is_branch=False):
        key = module.name + "_" + pin_name
        if key not in self.loads:
            self.loads[key] = GraphLoad(pin_name, module, wire_length=wire_length,
                                        count=count)
        else:
            self.loads[key].increment()
            self.loads[key].wire_length = max(wire_length, self.loads[key].wire_length)

    def items(self):
        return self.loads.items()

    def __str__(self):
        return "\n".join([str(x) for x in self.loads.values()])


class GraphNode:
    """Represent a node on a graph. Includes
            node net name
             the module it's an input to on the relevant path
             the pin it's an input to on the path"""

    def __init__(self, in_net: str, out_net: str, module: design,
                 parent_in_net: str, parent_out_net: str,
                 all_parent_modules: List[Tuple[design, List[str]]],
                 conn: List[str]):
        self.in_net = in_net
        self.out_net = out_net
        self.module = module
        self.parent_in_net = parent_in_net
        self.parent_out_net = parent_out_net

        self.parent_module = all_parent_modules[-1][0]
        self.original_parent_module = self.parent_module  # for when parent module is overridden at higher level
        self.all_parent_modules = all_parent_modules
        self.conn = conn

        conn_index = self.parent_module.conns.index(conn)
        self.instance = self.parent_module.insts[conn_index]
        self.instance_name = self.instance.name

        self.loads = GraphLoads()
        self.output_cap = 0.0
        self.driver_res = math.inf
        self.delay = None  # type: Union[None, delay_data]

        debug.info(3, "Created GraphNode: {}".format(str(self)))

    def get_next_load(self, next_node: 'GraphNode') -> Tuple[List[GraphLoad], Union[None, GraphLoad]]:

        if next_node is None:
            all_loads = list(self.loads.loads.values())
            if all_loads:
                return all_loads[1:], all_loads[0]
            return [], None

        other_loads = []

        next_node_load = None
        all_next_hierarchy = [x[0] for x in next_node.all_parent_modules] + [next_node.module]

        for load in self.loads.loads.values():
            load_name = load.module.name
            if next_node_load is not None:
                other_loads.append(load)
            else:
                # go from top of hierarchy to lowest. For example, check bank, then precharge array
                for module in all_next_hierarchy:
                    if module.name == load_name:
                        next_node_load = load
                        break
        return other_loads, next_node_load

    def evaluate_caps(self):
        total_cap = 0.0
        for _, load in self.loads.items():
            total_cap += load.evaluate_cin()
        self.output_cap = total_cap
        return total_cap

    def extract_loads(self, top_level_module: design, estimate_wire_lengths=True):
        """estimate_wire_lengths determines whether to estimate wire length based on physical distance
        # FIXME: Careful with this, some wires will be shared and this would "double-count" them
        """

        def get_loads_at_net(net: str, conn: List[str], module: design):
            """Gets all the nodes at net except the one at conn"""

            conn_index = module.conns.index(conn)
            net_index = conn.index(net)

            loads = []

            driver_inst = module.insts[conn_index]

            if net in module.pins:
                input_pin = module.get_pin(net)
                driver_pin = input_pin
            else:
                driver_pin_name = driver_inst.mod.pins[net_index]
                driver_pin = driver_inst.get_pin(driver_pin_name)
            for inst_index in range(len(module.conns)):
                module_conn = module.conns[inst_index]
                if net not in module_conn:
                    continue
                net_indices = [j for j, x in enumerate(module_conn) if x == net]
                for conn_net_index in net_indices:
                    if inst_index == conn_index and conn_net_index == net_index:
                        # original net we're tracing
                        continue
                    inst_mod = module.insts[inst_index].mod
                    pin_index = module_conn.index(net)
                    input_pin_name = inst_mod.pins[pin_index]
                    if estimate_wire_lengths:
                        inst_pin = module.insts[inst_index].get_pin(input_pin_name)
                        x_distance, y_distance = inst_pin.distance_from(driver_pin)
                        wire_length = x_distance + y_distance
                    else:
                        wire_length = 0.0
                    loads.append((input_pin_name, inst_mod, wire_length))
            return loads

        all_loads = []
        driver_conn = self.conn
        output_net = self.parent_out_net
        all_loads.extend(get_loads_at_net(output_net, driver_conn, self.original_parent_module))

        current_module = self.original_parent_module

        for ancestor_module, ancestor_conn in reversed(self.all_parent_modules[:-1]):
            if output_net not in current_module.pins:
                break
            # find corresponding output net
            output_pin_index = current_module.pins.index(output_net)
            output_net = ancestor_conn[output_pin_index]
            all_loads.extend(get_loads_at_net(output_net, ancestor_conn, ancestor_module))
            current_module = ancestor_module

            if ancestor_module.name == top_level_module.name:
                break
        for input_pin_name_, inst_mod_, wire_length_ in all_loads:
            self.loads.add_load(pin_name=input_pin_name_, module=inst_mod_, wire_length=wire_length_)

    def evaluate_resistance(self, corner=None):
        self.driver_res = self.module.get_driver_resistance(pin_name=self.out_net, corner=corner,
                                                            use_max_res=True)
        return self.driver_res

    def evaluate_delay(self, next_node: 'GraphNode', slew_in, corner=None, swing=0.5):
        other_loads, next_node_load = self.get_next_load(next_node)

        # Determine if this is a distributed load
        is_distributed = False
        if next_node_load:
            if next_node_load.is_distributed():
                is_distributed = True
                # only one of them will be on the critical path so add the others as regular loads
                if next_node_load.count > 1:
                    other_loads.extend([next_node_load] * (next_node_load.count - 1))
            else:
                is_distributed = False
                other_loads.append(next_node_load)
        # estimate non distributed cap
        load_caps = 0.0
        for load in other_loads:
            load_caps += load.evaluate_cin()

        intrinsic_cap, _ = self.module.get_input_cap(pin_name=self.out_net, num_elements=1,
                                                     wire_length=0)
        load_caps += intrinsic_cap

        # driver res
        driver_res = self.evaluate_resistance(corner=corner)
        driver_gm = self.module.evaluate_driver_gm(pin_name=self.out_net, corner=corner)

        if is_distributed:
            return self.evaluate_distributed_delay(driver_res, driver_gm, load_caps,
                                                   next_node_load, next_node, slew_in)
        else:  # Horowitz

            tau = load_caps * driver_res
            beta = 1 / (driver_gm * driver_res)
            alpha = slew_in / tau

            delay, slew_out = self.module.horiwitz_delay(tau, beta, alpha)

            self.delay = delay_data(delay, slew_out)
            return self.delay

    def evaluate_distributed_delay(self, driver_res: float, driver_gm: float, load_caps: float,
                                   next_node_load: GraphLoad, next_node: 'GraphNode',
                                   slew_in: float):
        instances_groups = next_node_load.module.group_pin_instances_by_mod(next_node_load.pin_name)
        # find the most relevant instance group.
        # Just a heuristic, getting more deterministic result is more complicated
        # If only one instance group, then answer is obvious
        # If one of the groups's module matches the module of the next_node, then choose that group
        # Otherwise choose the group with the maximum number of loads and add the others to regular caps
        if len(instances_groups) == 1:
            distributed_load = next(iter(instances_groups.values()))
        else:
            distributed_load = None
            other_internal_loads = []
            # use module name
            if next_node:
                for load in instances_groups.values():
                    if load[2].name == next_node.module.name:
                        distributed_load = load
                    else:
                        other_internal_loads.append(load)
            # still not found use count
            if distributed_load is None:
                other_internal_loads.clear()
                instance_groups_list = list(instances_groups.values())
                max_count_index = max(range(len(instance_groups_list)),
                                      key=lambda x: instance_groups_list[x][0])
                distributed_load = instance_groups_list[max_count_index]
                other_internal_loads = (instance_groups_list[:max_count_index] +
                                        instance_groups_list[max_count_index + 1:])
            # add other internal loads as regular caps
            for other_internal in other_internal_loads:
                graph_load = GraphLoad(pin_name=other_internal[1], module=other_internal[2],
                                       count=other_internal[0], wire_length=0.0)
                load_caps += graph_load.evaluate_cin()
            #
            input_pin = next_node_load.module.get_pin(next_node_load.pin_name)
            connecting_wire_length = next_node_load.wire_length
            connecting_wire_width = min(input_pin.width(), input_pin.height())
            additional_wire_cap = next_node_load.module.get_wire_cap(wire_layer=input_pin.layer,
                                                                     wire_width=connecting_wire_width,
                                                                     wire_length=connecting_wire_length)
            load_caps += additional_wire_cap
            additional_wire_res = next_node_load.module.get_wire_res(wire_layer=input_pin.layer,
                                                                     wire_width=connecting_wire_width,
                                                                     wire_length=connecting_wire_length)
            driver_res += additional_wire_res

        num_elements, pin_name, module = distributed_load
        input_pin = module.get_pin(pin_name)
        pin_length = max(max(input_pin.width(), input_pin.height()),
                         min(module.width, module.height))
        pin_width = min(input_pin.width(), input_pin.height())
        cap_per_unit, _ = module.get_input_cap(pin_name, num_elements=1, wire_length=pin_length,
                                               interpolate=False)
        res_per_stage = module.get_wire_res(wire_layer=input_pin.layer,
                                            wire_width=pin_width, wire_length=pin_length)
        delay, slew_out = module.distributed_delay(cap_per_unit, res_per_stage, num_elements,
                                                   driver_res, driver_gm, load_caps, slew_in)
        self.delay = delay_data(delay, slew_out)
        return self.delay

    def __str__(self):
        if self.delay is not None:
            delay_suffix = " ({:.3g} p) ".format(self.delay.delay * 1e12)
        else:
            delay_suffix = ""
        return " {}:{}-> | {}:{} | -> {}:{} {} ".format(self.parent_in_net, self.in_net,
                                                        self.instance_name,
                                                        self.module.name, self.parent_out_net,
                                                        self.out_net, delay_suffix)

    def __repr__(self):
        return self.__str__()


class GraphPath:
    """Represent a path of GraphNode from a source net to a destination net"""

    def __init__(self, nodes=None):
        self.nodes = nodes if nodes is not None else []  # type: List[GraphNode]
        debug.info(3, "Created GraphPath: {}".format(str(self)))

    def prepend_node(self, node: GraphNode):
        return GraphPath([node] + self.nodes)

    def prepend_nodes(self, path: "GraphPath"):
        nodes = path.nodes + self.nodes
        return GraphPath(nodes)

    def traverse_loads(self, estimate_wire_lengths=True, top_level_module=None):
        """
        :param estimate_wire_lengths: Use distance between pins as pin length
        :param top_level_module: check for loads to pins at hierarchies up to 'top_level_module'
        """
        if top_level_module is None:
            top_level_module = self.nodes[0].parent_module
        for graph_node in self.nodes:
            graph_node.extract_loads(estimate_wire_lengths=estimate_wire_lengths,
                                     top_level_module=top_level_module)

    def evaluate_delays(self, slew_in):
        for i in range(len(self.nodes)):
            if i == len(self.nodes) - 1:
                next_node = None
            else:
                next_node = self.nodes[i + 1]
            graph_node = self.nodes[i]
            delay_val = graph_node.evaluate_delay(next_node=next_node, slew_in=slew_in)
            slew_in = delay_val.slew

    def get_cin(self, pin_name):
        """Assumes first node's parent module is the real parent module"""
        # evaluate instance inputs
        source_node = self.nodes[0]
        parent_module = source_node.parent_module

        return parent_module.get_input_cap_from_instances(pin_name=pin_name)

    @property
    def source_node(self):
        return self.nodes[0]

    @source_node.setter
    def source_node(self, value):
        self.nodes[0] = value

    def __str__(self):
        return "\t".join([str(x) for x in self.nodes])

    def __repr__(self):
        result = ""
        for i in range(len(self.nodes)):
            if i < len(self.nodes) - 1:
                result += "{}\n{}".format(str(self.nodes[i]), 4 * (i + 1) * " ")
            else:
                result += str(self.nodes[-1])
        return result

    def __len__(self):
        return len(self.nodes)


def get_instance_module(instance_name: str, parent_module: design):
    """Get module for instance given the instance name"""
    instance_name = instance_name.lower()

    def name_matches(inst):
        candidate_name = inst.name.lower().strip()  # type: str
        return (candidate_name == instance_name or
                (instance_name and instance_name.startswith("x") and
                 instance_name[1:] == candidate_name))

    matches = list(filter(name_matches, parent_module.insts))
    if not matches:
        raise ValueError("Invalid instance name {} in module {}".format(instance_name, parent_module.name))

    return matches[0].mod


def get_net_hierarchy(net: str, parent_module: design):
    """Split net into hierarchy of parent modules
    e.g. inst1.inst2.out will split into [int1_mod, inst2_mod]
    :return [list of hierarchy]
    """
    net = net.lower()
    net_split = net.split(".")
    hierarchy = [parent_module]

    current_module = parent_module
    for branch in net_split[:-1]:
        child_module = get_instance_module(branch, current_module)
        hierarchy.append(child_module)
        current_module = child_module

    return net_split[-1], hierarchy


def get_net_driver(net: str, module: design):
    out_drivers, in_out_drivers = get_all_net_drivers(net, module)
    driver = None
    if out_drivers:
        driver = out_drivers[0]
    if in_out_drivers:
        driver = in_out_drivers[0]
    debug.info(4, "Driver for net {} in module {} is {}".format(net, module.name,
                                                                driver[1].name))
    return driver


def get_all_net_drivers(net: str, module: design, ):
    net = net.lower()
    # first check if there is an instance whose output is the pin, otherwise, settle for inout
    inout_drivers = []
    output_drivers = []
    for i in range(len(module.conns)):
        conn = [x.lower() for x in module.conns[i]]
        if net not in conn:
            continue
        child_module = module.insts[i].mod  # type: design
        pin_index = conn.index(net)
        child_pin = child_module.pins[pin_index]
        pin_dir = child_module.get_pin_dir(child_pin)
        candidate = (child_pin, child_module, module.conns[i])
        if pin_dir == OUTPUT:
            output_drivers.append(candidate)
        elif pin_dir == INOUT:
            inout_drivers.append(candidate)

    if not output_drivers + inout_drivers:
        raise ValueError("net {} not driven by an output or inout pin"
                         " in module {}".format(net, module.name))

    return output_drivers, inout_drivers


def get_all_drivers_for_pin(net: str, parent_module: design):
    output_drivers, inout_drivers = get_all_net_drivers(net, parent_module)
    all_drivers = output_drivers + inout_drivers
    results = []
    for child_pin, child_module, conn in all_drivers:
        if child_module.is_delay_primitive():
            results.append([parent_module, child_module, (child_pin, net, conn)])
        else:
            descendants = get_all_drivers_for_pin(child_pin, child_module)
            for desc_ in descendants:
                results.append([(parent_module, conn)] + desc_)
    return results


def get_driver_for_pin(net: str, parent_module: design):
    """Get hierarchy of modules driving a pin """
    child_pin, child_module, conn = get_net_driver(net, parent_module)

    if child_module.is_delay_primitive():
        return [parent_module, child_module, (child_pin, net, conn)]
    descendants = get_driver_for_pin(child_pin, child_module)
    return [(parent_module, conn)] + descendants


def construct_paths(driver_hierarchy, current_depth=0, max_depth=20, max_adjacent_modules=50,
                    driver_exclusions=None):
    """
    Construct list of GraphPath for all input pins to outputs
    :param driver_hierarchy: [mod1, mod2, ..., modn, (pin_name, net, conn)]
    :param current_depth: hierarchy depth
    :param max_depth: Max hierarchical depth, prevents infinite cyclic routes
    :param max_adjacent_modules: Max number of sibling modules to derive from. Prevents cyclic routes
    :param driver_exclusions: Check 'create_graph' for documentation
    :return: List[GraphPath]
    """

    if current_depth >= max_depth:
        raise ValueError("Max depth exceeded. Netlist potentially contains cycles"
                         " or try increasing max_depth from {}".format(max_depth))

    paths = []  # type: List[GraphPath]

    instance_pin_name, output_net, conn = driver_hierarchy[-1]
    driver_module = driver_hierarchy[-2]  # type: design
    immediate_parent_module = original_parent = driver_hierarchy[-3]

    parent_modules = driver_hierarchy[:-3]  # type: List[Tuple[design, List[str]]]

    input_pins = driver_module.get_input_pins()
    for pin in input_pins:
        pin_index = driver_module.pins.index(pin)
        parent_module_net = conn[pin_index]

        all_parent_modules = parent_modules + [(immediate_parent_module, conn)]
        graph_node = GraphNode(in_net=pin, out_net=instance_pin_name, module=driver_module,
                               parent_in_net=parent_module_net, parent_out_net=output_net,
                               all_parent_modules=all_parent_modules, conn=conn)
        paths.append(GraphPath([graph_node]))

    # Process derived inputs by descending into modules that created them
    processing_queue = [x for x in paths]  # quick copy
    processed_paths = []

    sibling_iterations_count = 0
    while len(processing_queue) > 0:
        path = processing_queue[0]

        source_node = path.source_node
        if source_node.parent_in_net in immediate_parent_module.pins:  # not a derived node
            # check if it's explicitly an input
            if immediate_parent_module.get_pin_dir(source_node.parent_in_net) == INPUT:
                processed_paths.append(path)
                processing_queue.remove(path)
                continue

        # find module that drives this net within the current hierarchy
        sibling_out_pin, sibling_module, sibling_conn = get_net_driver(
            source_node.parent_in_net, immediate_parent_module)
        sibling_input_pins = sibling_module.get_input_pins()

        if sibling_module.is_delay_primitive():
            for sibling_input_pin in sibling_input_pins:
                sibling_pin_index = sibling_module.pins.index(sibling_input_pin)
                all_parent_modules = parent_modules + [(immediate_parent_module, sibling_conn)]
                sibling_node = GraphNode(in_net=sibling_input_pin, out_net=sibling_out_pin,
                                         module=sibling_module,
                                         parent_in_net=sibling_conn[sibling_pin_index],
                                         parent_out_net=source_node.parent_in_net,
                                         all_parent_modules=all_parent_modules, conn=sibling_conn)
                new_path = path.prepend_node(sibling_node)
                processing_queue.append(new_path)
        else:
            sibling_hierarchy = get_driver_for_pin(sibling_out_pin, sibling_module)
            sibling_paths = construct_paths(sibling_hierarchy, current_depth=current_depth + 1,
                                            max_depth=max_depth,
                                            max_adjacent_modules=max_adjacent_modules)
            for sibling_path in sibling_paths:
                new_path = path.prepend_nodes(sibling_path)
                processing_queue.append(new_path)

        processing_queue.remove(path)

        sibling_iterations_count += 1
        if sibling_iterations_count > max_adjacent_modules:
            raise ValueError("max_adjacent_modules exceeded. Netlist potentially contains cycles"
                             " or try increasing max_adjacent_modules from {}".format(max_adjacent_modules))

    final_paths = processed_paths

    # Process ancestors
    all_ancestors = list(reversed(parent_modules))
    for i in range(len(all_ancestors)):
        ancestor_module, ancestor_conn = all_ancestors[i]
        processing_queue = [x for x in processed_paths]
        processed_paths = []
        for path in processing_queue:
            source_node = path.source_node
            child_pin_index = immediate_parent_module.pins.index(source_node.parent_in_net)
            pin_net_in_ancestor = ancestor_conn[child_pin_index]
            if pin_net_in_ancestor in ancestor_module.pins:
                source_node.parent_in_net = pin_net_in_ancestor
                source_node.parent_module = ancestor_module
                processed_paths.append(path)
            else:
                # derive the path
                all_drivers_in_ancestor = get_all_net_drivers(pin_net_in_ancestor, ancestor_module)
                for driver_in_ancestor in all_drivers_in_ancestor[0] + all_drivers_in_ancestor[1]:
                    next_driver_pin, next_driver_module, next_driver_conns = driver_in_ancestor
                    next_driver_paths = create_graph(next_driver_pin, next_driver_module,
                                                     driver_exclusions)
                    sibling_immediate_parent = (all_ancestors[i][0], next_driver_conns)
                    sibling_all_parent_modules = list(reversed(all_ancestors[i + 1:])) + [sibling_immediate_parent]
                    for next_driver_path in next_driver_paths:
                        for node in next_driver_path.nodes:
                            node.all_parent_modules = sibling_all_parent_modules + node.all_parent_modules
                        processed_paths.append(path.prepend_nodes(next_driver_path))

        immediate_parent_module = ancestor_module
        final_paths = processed_paths

    debug.info(2, "Derived path for {} in {}:".format(output_net, original_parent.name))
    for path in final_paths:
        debug.info(2, str(path))
    return final_paths


def create_graph(destination_net, module: design, driver_exclusions=None):
    """
    Create a list of GraphPath from all input pins to destination_net
    :param destination_net: destination_net
    :param module: The module to derive. Should be a subclass of 'design'
    :param driver_exclusions: the drivers to exclude from derivation.
            This is useful for nets that are driven by multiple nodes
            For example, bitlines are driven by precharge, bitcells, write_driver etc
            Exclude bitcells from path by adding e.g. cell_6t to driver_exclusions
    :return: List[GraphPath]
    """
    if driver_exclusions is None:
        driver_exclusions = []
    destination_net, dest_hierarchy = get_net_hierarchy(destination_net, module)
    all_paths = []
    for driver_hierarchy in get_all_drivers_for_pin(destination_net, dest_hierarchy[-1]):
        if driver_hierarchy[-2].name not in driver_exclusions:
            all_paths.extend(construct_paths(driver_hierarchy, driver_exclusions=driver_exclusions))

    return all_paths
