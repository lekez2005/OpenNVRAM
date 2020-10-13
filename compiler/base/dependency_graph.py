from typing import List, Tuple

import debug
from base.design import design
from base.hierarchy_spice import OUTPUT, INOUT


class GraphNode:
    """Represent a node on a graph. Includes
            node net name
             the module it's an input to on the relevant path
             the pin it's an input to on the path"""

    def __init__(self, in_net: str, out_net: str, module: design,
                 parent_in_net: str, parent_out_net: str, parent_module: design):
        self.in_net = in_net
        self.out_net = out_net
        self.module = module
        self.parent_in_net = parent_in_net
        self.parent_out_net = parent_out_net
        self.parent_module = parent_module

    def __str__(self):
        return " {}:{}-> | {} | -> {}:{} ".format(self.parent_in_net, self.in_net,
                                                  self.module.name, self.parent_out_net,
                                                  self.out_net)

    def __repr__(self):
        return self.__str__()


class GraphPath:
    """Represent a path of GraphNode from a source net to a destination net"""

    def __init__(self, nodes=None):
        self.nodes = nodes if nodes is not None else []  # type: List[GraphNode]

    def prepend_node(self, node: GraphNode):
        return GraphPath([node] + self.nodes)

    def prepend_nodes(self, path: "GraphPath"):
        nodes = path.nodes + self.nodes
        return GraphPath(nodes)

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
    net = net.lower()
    # first check if there is an instance whose output is the pin, otherwise, settle for inout
    inout_candidate = None
    output_candidate = None
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
            output_candidate = candidate
            break
        elif pin_dir == INOUT:
            inout_candidate = candidate

    if output_candidate is None:
        output_candidate = inout_candidate
    if output_candidate is None:
        raise ValueError("net {} not driven by an output or inout pin"
                         " in module {}".format(net, module.name))
    debug.info(4, "Driver for net {} in module {} is {}".format(net, module.name,
                                                                output_candidate[1].name))
    return output_candidate


def get_driver_for_pin(net: str, parent_module: design):
    """Get hierarchy of modules driving a pin """
    child_pin, child_module, conn = get_net_driver(net, parent_module)

    if child_module.is_delay_primitive():
        return [parent_module, child_module, (child_pin, net, conn)]
    descendants = get_driver_for_pin(child_pin, child_module)
    return [(parent_module, net, conn)] + descendants


def construct_paths(driver_hierarchy, index=0, max_depth=20, max_adjacent_modules=50):
    """
    Construct list of GraphPath for all input pins to outputs
    :param driver_hierarchy: [mod1, mod2, ..., modn, (pin_name, net, conn)]
    :param index: hierarchy depth
    :param max_depth: Max hierarchical depth, prevents infinite cyclic routes
    :param max_adjacent_modules: Max number of sibling modules to derive from. Prevents cyclic routes
    :return: List[GraphPath]
    """

    if index >= max_depth:
        raise ValueError("Max depth exceeded. Netlist potentially contains cycles"
                         " or try increasing max_depth from {}".format(max_depth))

    paths = []  # type: List[GraphPath]

    instance_pin_name, output_net, conn = driver_hierarchy[-1]
    driver_module = driver_hierarchy[-2]  # type: design
    immediate_parent_module = original_parent = driver_hierarchy[-3]

    parent_modules = driver_hierarchy[:-3]  # type: List[Tuple[design, str, List[str]]]

    input_pins = driver_module.get_input_pins()
    for pin in input_pins:
        pin_index = driver_module.pins.index(pin)
        parent_module_net = conn[pin_index]

        graph_node = GraphNode(in_net=pin, out_net=instance_pin_name, module=driver_module,
                               parent_in_net=parent_module_net, parent_out_net=output_net,
                               parent_module=immediate_parent_module)
        paths.append(GraphPath([graph_node]))

    # Process derived inputs by descending into modules that created them
    processing_queue = [x for x in paths]  # quick copy
    processed_paths = []

    sibling_iterations_count = 0
    while len(processing_queue) > 0:
        path = processing_queue[0]

        source_node = path.source_node
        if source_node.parent_in_net in immediate_parent_module.pins:  # not a derived node
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

                sibling_node = GraphNode(in_net=sibling_input_pin, out_net=sibling_out_pin,
                                         module=sibling_module,
                                         parent_in_net=sibling_conn[sibling_pin_index],
                                         parent_out_net=source_node.parent_in_net,
                                         parent_module=immediate_parent_module)
                new_path = path.prepend_node(sibling_node)
                processing_queue.append(new_path)
        else:
            sibling_hierarchy = get_driver_for_pin(sibling_out_pin, sibling_module)
            sibling_paths = construct_paths(sibling_hierarchy, index=index + 1, max_depth=max_depth,
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
    for ancestor_module, ancestor_net, ancestor_conn in reversed(parent_modules):
        processing_queue = [x for x in processed_paths]
        processed_paths = []
        for path in processing_queue:
            source_node = path.source_node
            child_pin_index = immediate_parent_module.pins.index(source_node.parent_in_net)
            pin_net_in_ancestor = ancestor_conn[child_pin_index]
            if pin_net_in_ancestor in ancestor_module.pins:
                source_node.parent_in_net = pin_net_in_ancestor
                processed_paths.append(path)
            else:
                # derive the path
                next_driver_pin, next_driver_module, next_driver_conns = \
                    get_net_driver(pin_net_in_ancestor, ancestor_module)
                next_driver_hierarchy = [ancestor_module, next_driver_module,
                                         (next_driver_pin, pin_net_in_ancestor, next_driver_conns)]
                parent_paths = construct_paths(next_driver_hierarchy, 0, max_depth=max_depth,
                                               max_adjacent_modules=max_adjacent_modules)
                for parent_path in parent_paths:
                    processed_paths.append(path.prepend_nodes(parent_path))

        immediate_parent_module = ancestor_module
        final_paths = processed_paths

    debug.info(2, "Derived path for {} in {}:".format(output_net, original_parent.name))
    for path in final_paths:
        debug.info(2, str(path))
    return final_paths


def create_graph(destination_net, module: design):
    """
    Create a list of GraphPath from all input pins to destination_net
    :param destination_net: destination_net
    :param module:
    :return: List[GraphPath]
    """
    destination_net, dest_hierarchy = get_net_hierarchy(destination_net, module)
    dest_driver_hierarchy = get_driver_for_pin(destination_net, dest_hierarchy[-1])
    return construct_paths(dest_driver_hierarchy)
