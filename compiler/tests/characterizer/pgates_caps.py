#!/usr/bin/env python3
import json
import os
import pathlib
import re

import numpy as np

from char_test_base import CharTestBase
from characterization_utils import beta_regex

ACTION_SINGLE = "single"
ACTION_SWEEP = "sweep"
ACTION_PLOT = "plot"

PINV = "pinv"
PNAND2 = "pnand2"
PNAND3 = "pnand3"
PNOR2 = "pnor2"

CIN = "cin"


class PgateCaps(CharTestBase):
    buffer_stages = [1, 2]

    @classmethod
    def add_additional_options(cls):
        cls.parser.add_argument("--driver_size", default=4, type=float)
        cls.parser.add_argument("-a", "--action", default=ACTION_PLOT,
                                choices=[ACTION_SINGLE, ACTION_SWEEP])
        cls.parser.add_argument("--gate", default=None,
                                choices=[PINV, PNAND2, PNAND3, PNOR2])
        cls.parser.add_argument("-s", "--size",
                                default=1, type=float, help="Inverter size")
        cls.parser.add_argument("--max_size",
                                default=50, type=float, help="Max inverter size")
        cls.parser.add_argument("--num_sizes",
                                default=20, type=float, help="Number of sizes to sweep")

    def test_single_sim(self):
        import debug
        if not self.options.action == ACTION_SINGLE:
            return
        self.options.pin_name = "A"
        cap_val, dut = self.run_sim()
        num_fingers = dut.tx_mults
        debug.info(0, "Size = {:.3g}, fingers = {}".format(self.options.size, num_fingers))
        debug.info(0, "Cap = {}fF".format(cap_val * 1e15))
        debug.info(0, "Cap per unit inverter = {}fF".format(cap_val * 1e15 / self.options.size))

    def test_sweep(self):

        from base.design import design

        if not self.options.action == ACTION_SWEEP:
            return

        if self.options.gate is None:
            all_gates = [PNAND2, PNAND3, PNOR2, PINV]
        else:
            all_gates = [self.options.gate]

        for gate in all_gates:
            print("\n{}:".format(gate.upper()))
            self.options.gate = gate

            if gate == PINV:
                max_log = np.log10(self.options.max_size)
                sizes = np.logspace(0, max_log, self.options.num_sizes)
                # sizes = np.linspace(1, self.options.max_size, self.options.num_sizes)
                pins = ["A"]
            else:
                # sizes = [self.options.size]
                sizes = [1, 1.5, 2]
                if gate in [PNAND2, PNOR2]:
                    pins = ["A", "B"]
                else:
                    pins = ["A", "B", "C"]

            for size in sizes:
                print("  size: {:.3g}:".format(size))
                self.options.size = size

                for pin_name in pins:
                    self.options.pin_name = pin_name
                    design.name_map.clear()
                    try:
                        cap_val, dut = self.run_sim()
                    except AssertionError as ex:
                        if str(ex).startswith("Only Single"):
                            # ignore if size doesn't fit height
                            continue
                        else:
                            raise ex

                    cap_per_size = cap_val / size

                    file_suffixes = [("beta", self.options.beta)]
                    if not self.options.horizontal:
                        file_suffixes.append(("contacts", int(not self.options.no_contacts)))

                    size_suffixes = [("height", dut.height)]
                    self.save_result(gate, pin_name.lower(), value=cap_per_size, size=size,
                                     file_suffixes=file_suffixes, size_suffixes=size_suffixes)
                    print("    {}:\t Cap = {:5.5g} fF".format(
                        pin_name, 1e15 * cap_val / size))

                    if pin_name == "A":
                        # Z pin
                        _, cap_per_unit = dut.compute_input_cap("z")
                        self.save_result(gate, "z", value=cap_per_unit, size=size,
                                         file_suffixes=file_suffixes, size_suffixes=size_suffixes)

    @staticmethod
    def get_pgate_params(gate, pin_name, size, height, options):

        from pgates.pinv import pinv
        from pgates.pnand2 import pnand2
        from pgates.pnand3 import pnand3
        from pgates.pnor2 import pnor2

        if options.horizontal:
            from modules.horizontal.pinv_horizontal import pinv_horizontal
            from modules.horizontal.pnand2_horizontal import pnand2_horizontal
            from modules.horizontal.pnor2_horizontal import pnor2_horizontal
            from modules.horizontal.pnand3_horizontal import pnand3_horizontal
            modules_dict = {
                PINV: pinv_horizontal,
                PNAND2: pnand2_horizontal,
                PNAND3: pnand3_horizontal,
                PNOR2: pnor2_horizontal
            }
            module_args = {"size": size}
        else:
            modules_dict = {
                PINV: pinv,
                PNAND2: pnand2,
                PNAND3: pnand3,
                PNOR2: pnor2
            }
            module_args = {"size": size, "height": height,
                           "contact_nwell": not options.no_contacts,
                           "contact_pwell": not options.no_contacts}

        mod = modules_dict[gate]

        if gate == PINV:
            num_inputs = 1
        elif gate == PNAND3:
            num_inputs = 3
        else:
            num_inputs = 2

        all_input_pins = ["A", "B", "C"]

        if gate == PNOR2:
            in_pins = ["gnd"]  # so switch happens depending on tested pin input
        else:
            in_pins = ["vdd"] * (num_inputs - 1)
        in_pins.insert(all_input_pins.index(pin_name), "d")
        terminals = in_pins + ["f", "vdd", "gnd"]

        return mod, module_args, terminals

    def run_sim(self):
        from globals import OPTS

        self.driver_size = self.options.driver_size

        gate = self.options.gate
        size = self.options.size
        pin_name = self.options.pin_name

        sim_dir = "{}_beta_{:.3g}".format(gate, self.options.beta)
        self.set_temp_folder(sim_dir)

        height = self.options.height or OPTS.logic_buffers_height
        mod, module_args, terminals = self.get_pgate_params(gate, pin_name, size, height, self.options)
        connections = " ".join(terminals)

        dut = mod(**module_args)
        if self.options.no_contacts or self.options.horizontal:
            dut = self.wrap_pgate()

        dut_pex = self.run_pex_extraction(dut, dut.name)

        self.load_pex = dut_pex
        self.dut_name = dut.name

        self.dut_instance = "X4 {connections}    {dut_name}          * real load".format(
            connections=connections, dut_name=self.dut_name)

        # total_cap = self.run_ac_cap_measurement(pin_name, dut)
        self.run_optimization()
        total_cap = self.get_optimization_result()
        return total_cap, dut

    def test_plot(self):

        from matplotlib import pyplot as plt

        if not self.options.plot:
            return
        results_dir = self.get_char_data_file("")

        save_dir = self.get_char_data_file("inverter_cin")
        if not os.path.exists(save_dir):
            pathlib.Path(save_dir).mkdir(parents=True, exist_ok=True)

        valid_files = list(filter(lambda x: x.startswith("pinv"), os.listdir(results_dir)))

        sorted_files = list(sorted(valid_files, key=beta_regex))

        for f in sorted_files:
            beta = beta_regex(f)
            with open(os.path.join(results_dir, f), "r") as result_file:
                data = json.load(result_file)
            gate_cap_data = data["A"]
            # group by properties other than size
            characterization_groups = {}
            for key, val in gate_cap_data.items():
                match = re.search(r"(.*)size_([0-9\.]+)_?(.*)", key)

                other_properties = match.groups()[0] + match.groups()[2]
                size = float(match.groups()[1])
                if other_properties not in characterization_groups:
                    characterization_groups[other_properties] = []
                characterization_groups[other_properties].append([size, val])
            for key, val in characterization_groups.items():
                val = list(sorted(val, key=lambda x: x[0]))

                full_legend = r"{}$\beta$={:.3g}".format(key, beta)
                plt.plot([x[0] for x in val], [x[1]*1e15 for x in val], '-+', label=full_legend)

        plt.grid()
        plt.xlabel("Inverter size")
        plt.ylabel("Cap per unit size (fF)")

        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, "inverter_cin.png"))
        plt.savefig(os.path.join(save_dir, "inverter_cin.pdf"))
        plt.show()


PgateCaps.run_tests(__name__)
