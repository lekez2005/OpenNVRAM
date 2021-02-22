#!env python3

"""
Compare nvsim estimation to actual extracted simulations
"""
import json
import os
from importlib import reload

import numpy as np

from char_test_base import CharTestBase

ACTION_SIM = "sim"
ACTION_PLOT = "plot"
ACTION_ESTIMATE = "estimate"

precharge_size = 3
nvsim_dir = os.path.join(os.environ["RESEARCH_HOME"], "git", "NVSim", "results")

nvsim_results_file = os.path.join(nvsim_dir, "precharge_sweep.txt")
cadence_results_file = os.path.join(nvsim_dir, "cadence_results.json")
openram_estimate_file = os.path.join(nvsim_dir, "openram_estimate.json")
openram_dist = os.path.join(nvsim_dir, "openram_estimate_dist.json")
openram_horo = os.path.join(nvsim_dir, "openram_estimate_horo.json")


def load_nvsim():
    with open(nvsim_results_file, "r") as in_file_:
        results = []
        lines = in_file_.readlines()
        for i in range(0, len(lines), 2):
            first_line = lines[i].strip(" ,\n").split(",")
            second_line = lines[i + 1].strip(" ,\n").split(",")
            num_cols = int(second_line[0])
            sizes = list(map(float, first_line))
            delays = list(map(float, second_line[1:]))
            results.append((num_cols, sizes, delays))
        return results


spice_template = """
Vgnd gnd 0 0
Vdd vdd gnd {vdd_value}
Vin a gnd pulse {vdd_value} 0 50ps 10ps 10ps
* Vin_bar a_bar gnd pulse 0 {vdd_value} 50ps 10ps 10ps
Xdut a vdd vdd vdd gnd {wl_connections} {dut_name}

* set initial conditions via caps
Cbl {bl_probe} 0 c=0.01f ic=0
Cbr {br_probe} 0 c=0.01f ic=0
Cen {en_probe} 0 c=0.01f ic=0

{probes}

.measure tran en_time TRIG v(a) VAL='0.5*{vdd_value}' FALL=1 TARG v({en_probe}) VAL='{rise_end}' RISE=1
.measure tran bl_time TRIG v(a) VAL='0.5*{vdd_value}' FALL=1 TARG v({bl_probe}) VAL='{rise_end}' RISE=1
.measure tran br_time TRIG v(a) VAL='0.5*{vdd_value}' FALL=1 TARG v({br_probe}) VAL='{rise_end}' RISE=1
"""


class NVSimComparison(CharTestBase):

    @classmethod
    def add_additional_options(cls):
        cls.parser.add_argument("-a", "--action", default=ACTION_ESTIMATE,
                                choices=[ACTION_PLOT, ACTION_SIM, ACTION_ESTIMATE])
        cls.parser.add_argument("--linear", action="store_true")
        cls.parser.add_argument("--use_ultrasim", action="store_true")
        cls.parser.add_argument("--sim_length", default=500e-12, type=float)
        cls.parser.add_argument("--num_probes", default=8, type=int)
        cls.parser.add_argument("--num_elements", default=None, type=int)

    def test_plot(self):
        import matplotlib.pyplot as plt
        if not self.options.action == ACTION_PLOT and not self.options.plot:
            return
        nvsim_results = load_nvsim()
        nvsim_results = {x[0]: x[2] for x in nvsim_results}

        def load_data(file_name):
            with open(os.path.join(nvsim_dir, file_name + ".json"), "r") as f_:
                results = json.load(f_)
            return {key: [val[0], 0.5 * (val[1] + val[2])] for key, val in results.items()}

        all_data_files = ["cadence_results_spectre", "cadence_results_hspice",
                          "cadence_results_ultrasim",
                          "openram_estimate_horo", "openram_estimate_dist"]

        all_results = list(map(load_data, all_data_files)) + [nvsim_results]

        legends = ["spectre", "hspice", "ultrasim", "Dist-Horowitz", "Dist-RC", "NVSim"]
        plot_styles = ["-*", "-*", "-*", "o", "^", "+"]
        plot_func = "semilogx" if self.options.linear else "loglog"

        fig, subplots = plt.subplots(nrows=1, ncols=2, sharey=True, figsize=[8, 5])
        for i in range(len(all_results)):
            data = all_results[i]
            label = legends[i]
            style = plot_styles[i]
            en_delays = np.array([[int(key), value[0] * 1e9] for key, value in data.items()])
            getattr(subplots[0], plot_func)(en_delays[:, 0], en_delays[:, 1],
                                            style, label=label)
            bl_delays = np.array([[int(key), value[1] * 1e9] for key, value in data.items()])
            getattr(subplots[1], plot_func)(bl_delays[:, 0], bl_delays[:, 1],
                                            style, label=label)

        titles = ["Enable Delay", "Precharge Delay"]
        for i in range(2):
            subplots[i].set_xlabel("Number of elements")
            subplots[i].set_title(titles[i])
            subplots[i].legend()
            subplots[i].grid()
        subplots[0].set_ylabel("Delay (ns)")
        plt.tight_layout()
        plt.show()

    def get_simulation_elements(self):
        nvsim_results = load_nvsim()
        all_num_elements = [x[0] for x in nvsim_results]
        if self.options.num_elements is not None:
            num_elements_index = all_num_elements.index(self.options.num_elements)
            sim_elements = nvsim_results[num_elements_index: num_elements_index + 1]
        else:
            sim_elements = nvsim_results
        return sim_elements

    @staticmethod
    def save_data_point(results_file, num_elements, en_time, bl_time, br_time):
        if not os.path.exists(results_file):
            with open(results_file, "w") as data_file:
                json.dump({}, data_file)

        with open(results_file, "r") as data_file:
            existing_data = json.load(data_file)

        existing_data[str(num_elements)] = [en_time, bl_time, br_time]
        with open(results_file, "w") as data_file:
            json.dump(existing_data, data_file, indent=2)

    def test_estimate_delay(self):
        from characterizer.dependency_graph import create_graph
        from base.design import design
        from globals import OPTS
        if not self.options.action == ACTION_ESTIMATE:
            return

        c = __import__(OPTS.bitcell)
        bitcell = getattr(c, OPTS.bitcell)()
        bitcell_name = bitcell.name

        sim_elements = self.get_simulation_elements()
        for num_elements, sizes, delays in sim_elements:
            dut = self.make_dut(num_elements, sizes)
            output_pin = "bl[{}]".format(num_elements - 1)

            graph = create_graph(output_pin, dut, driver_exclusions=[bitcell_name])
            in_to_bl_path = graph[0]

            in_to_bl_path.traverse_loads(estimate_wire_lengths=True)
            in_to_bl_path.evaluate_delays(slew_in=10e-12)

            enable_delay = sum([x.delay.delay for x in in_to_bl_path.nodes[:-1]])
            bl_delay = in_to_bl_path.nodes[-1].delay.delay

            self.save_data_point(openram_estimate_file, num_elements, enable_delay, bl_delay,
                                 bl_delay)
            print("Num elements = {}".format(num_elements))
            design.name_map.clear()  # to prevent GDS uniqueness errors

    def test_sweep(self):
        if not self.options.action == ACTION_SIM:
            return

        from base.design import design
        from characterizer import stimuli
        from globals import OPTS

        import characterizer
        reload(characterizer)

        OPTS.spectre_ic_mode = "dev"
        OPTS.use_pex = True
        OPTS.use_ultrasim = self.options.use_ultrasim

        vdd_value = self.corner[1]

        sim_length = self.options.sim_length

        sim_elements = self.get_simulation_elements()

        min_num_elements = min([x[0] for x in sim_elements])

        for num_elements, sizes, delays in sim_elements:

            dut = self.make_dut(num_elements, sizes)
            # self.local_check(dut)
            pex_file = self.run_pex_extraction(dut, dut.name, run_drc=self.options.run_drc_lvs,
                                               run_lvs=self.options.run_drc_lvs)

            last_index = num_elements - 1

            en_template = "Xdut.N_en_Xprecharge_array_Xpre_{}_Xinv_Mpinv_nmos_g"
            bl_template = "Xdut.N_bl[{}]_Xbitcell_array_Xbit_r{{}}_c0_m1_d".format(last_index)
            br_template = "Xdut.N_br[{}]_Xbitcell_array_Xbit_r{{}}_c0_m2_d".format(last_index)
            vdd_pre_template = "Xdut.N_vdd_precharge_Xprecharge_array_Xpre_{}_Xprecharge_Mbl_pmos_s"
            gnd_pre_template = "Xdut.N_gnd_Xprecharge_array_Xpre_{}_Xinv_Mpinv_nmos_s"

            probe_templates = [en_template, bl_template, br_template, vdd_pre_template,
                               gnd_pre_template]

            all_probes = []

            bl_probe = br_probe = en_probe = vdd_precharge_probe = None

            probe_indices = set(np.linspace(0, last_index, self.options.num_probes).tolist() +
                                [0, last_index])

            for index in probe_indices:
                probes_ = [x.format(int(index)) for x in probe_templates]
                all_probes.extend(probes_)
                if index == num_elements - 1:
                    en_probe, bl_probe, br_probe, vdd_precharge_probe, _ = probes_
            probes = "\n".join([".probe v({})".format(x) for x in all_probes])

            # connect all wl to gnd
            wl_connections = " ".join(["gnd"] * num_elements)

            args = {
                "sim_length": sim_length,
                "vdd_value": vdd_value,
                "rise_end": 0.5 * vdd_value,
                "dut_name": dut.name,
                "wl_connections": wl_connections,
                "en_probe": en_probe,
                "bl_probe": bl_probe,
                "br_probe": br_probe,
                "probes": probes,
                "vdd_precharge_probe": vdd_precharge_probe,
                "TEMPERATURE": self.corner[2],
            }

            self.stim_file_name = self.prefix("stim.sp")

            with open(self.stim_file_name, "w") as stim_file:

                stim = stimuli(stim_file, corner=self.corner)
                stim.write_include(pex_file)
                spice_content = spice_template.format(**args)
                stim_file.write(spice_content)

                stim.write_control(sim_length * 1e9)

            stim.run_sim()

            search_func = search_meas
            if self.options.spice_name == "hspice":
                meas_file = self.prefix("timing.mt0")
            elif self.options.use_ultrasim:
                meas_file = self.prefix("stim.meas0")
                search_func = search_meas_usim
            else:
                meas_file = self.prefix("stim.measure")

            en_time = float(search_func("en_time", meas_file))
            bl_time = float(search_func("bl_time", meas_file))
            br_time = float(search_func("br_time", meas_file))

            if OPTS.use_ultrasim:
                suffix = "ultrasim"
            else:
                suffix = self.options.spice_name
            results_file = cadence_results_file.replace("cadence_results",
                                                        "cadence_results_" + suffix)
            self.save_data_point(results_file, num_elements, en_time, bl_time - en_time,
                                 br_time - en_time)

            design.name_map.clear()  # to prevent GDS uniqueness errors
            sim_length = self.options.sim_length + bl_time * num_elements / min_num_elements

    def estimate_delay(self, num_elements):
        pass

    def run_sim(self, num_elements):
        pass

    def make_dut(self, num_elements, buffer_stages):
        from base.design import design, METAL1, METAL2, PIMP, NWELL
        from base.vector import vector
        from base import utils
        from base.well_implant_fills import create_wells_and_implants_fills
        from base.contact import m1m2
        from globals import OPTS
        from modules.buffer_stage import BufferStage
        from modules.bitcell_array import bitcell_array
        from modules.precharge import precharge
        from pgates.pinv import pinv
        from tech import parameter, drc

        test_class_self = self

        c = __import__(OPTS.bitcell)
        bitcell = getattr(c, OPTS.bitcell)()

        class InverterExtendContactActive(pinv):
            """Extend inverter active to prevent minimum spacing issues"""

            def add_body_contacts(self):
                self.well_contact_active_width = bitcell.width
                super().add_body_contacts()

        class PrechargeNoEn(precharge):
            """Precharge cell without extending en pin across cell and no nwell contacts"""

            def add_layout_pin_center_rect(self, text, layer, offset, width=None, height=None):
                """Prevent adding en pin"""
                if text == "en":
                    return
                super().add_layout_pin_center_rect(text, layer, offset, width, height)

            def connect_input_gates(self):
                super().connect_input_gates()
                en_m1_rect = self.en_m1_rect
                self.add_layout_pin("en", METAL1, offset=en_m1_rect.offset,
                                    width=en_m1_rect.width, height=en_m1_rect.height)

            def add_active_contacts(self):
                super().add_active_contacts()
                # extend vdd to the inverter vdd
                vdd_x = [0, self.width - self.m1_width]
                for x_offset in vdd_x:
                    self.add_rect(METAL1, offset=vector(x_offset, self.contact_y),
                                  height=self.height - self.contact_y)
                vdd_x = self.source_drain_pos[1] - 0.5 * self.m1_width
                self.add_rect(METAL1, offset=vector(vdd_x, self.contact_y),
                              height=self.height - self.contact_y)

            def add_nwell_contacts(self):
                # inverter implant extends by 0.5*min_width_implant
                pimplant = self.get_layer_shapes(PIMP)[0]
                implant_height = self.height - pimplant.uy() - 0.5 * drc["minwidth_implant"]
                self.add_rect("pimplant", offset=vector(self.mid_x - 0.5 * self.implant_width,
                                                        pimplant.uy()),
                              width=self.implant_width,
                              height=implant_height)

        class PrechargeInverter(design):
            def __init__(self):
                self.name = "precharge_cell_{:.4g}".format(precharge_size).replace(".", "__")
                super().__init__(self.name)

                self.create_layout()

            def create_layout(self):
                self.add_pins()

                self.width = bitcell.width
                self.create_inverter()
                self.add_inverter()
                self.add_precharge()

                # en_bar to en
                en_bar = self.inv_inst.get_pin("Z")
                en = self.precharge_inst.get_pin("en")

                self.add_rect(METAL2, offset=en_bar.ul(), height=en.by() - en_bar.uy() + self.m2_width)
                self.add_rect(METAL2, offset=vector(en.cx(), en.by()),
                              width=en_bar.lx() + self.m2_width - en.cx())

                self.copy_layout_pin(self.precharge_inst, "bl", "bl")
                self.copy_layout_pin(self.precharge_inst, "br", "br")

                self.height = self.precharge_inst.uy()

            def create_inverter(self):
                # create smallest height inverter
                height = bitcell.height * 0.5
                while True:
                    try:
                        self.inv = InverterExtendContactActive(size=1, height=height,
                                                               contact_nwell=True,
                                                               contact_pwell=True)
                        self.add_mod(self.inv)
                        break
                    except AttributeError:
                        height *= 1.2

            def add_inverter(self):
                x_offset = 0.5 * (self.width - self.inv.width)

                self.inv_inst = self.add_inst("inv", mod=self.inv, offset=vector(x_offset, 0))
                self.connect_inst(["en", "en_bar", "vdd", "gnd"])

                for pin_name in ["vdd", "gnd"]:
                    self.copy_layout_pin(self.inv_inst, pin_name, pin_name)

                # en pin
                a_pin = self.inv_inst.get_pin("A")
                self.add_contact_center(layers=m1m2.layer_stack, offset=a_pin.center(),
                                        rotate=90)
                self.add_layout_pin_center_rect("en", METAL2, offset=a_pin.center())

            def add_precharge(self):
                name = "precharge_no_en_{:.4g}".format(precharge_size).replace(".", "__")
                actual_size = precharge_size / parameter["beta"]

                self.precharge = PrechargeNoEn(name, size=actual_size)
                self.add_mod(self.precharge)

                y_offset = self.inv_inst.uy() + self.precharge.height
                precharge_inst = self.add_inst("precharge", self.precharge,
                                               offset=vector(0, y_offset),
                                               mirror="MX")
                self.precharge_inst = precharge_inst
                self.connect_inst(["bl", "br", "en_bar", "vdd"])

            def add_pins(self):
                self.add_pin_list(["bl", "br", "en", "vdd", "gnd"])

        class PrechargeArray(design):
            def __init__(self):
                self.name = "precharge_array_{}_{:.4g}".format(num_elements, precharge_size)
                self.name = self.name.replace(".", "__")
                self.size = precharge_size
                self.columns = num_elements
                super().__init__(self.name)
                self.create_layout()

            def create_layout(self):
                self.add_pins()
                self.precharge_cell = PrechargeInverter()
                self.add_mod(self.precharge_cell)

                (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.columns)

                for i in range(self.columns):
                    name = "pre_{0}".format(i)
                    offset = vector(self.bitcell_offsets[i], 0)
                    inst = self.add_inst(name=name, mod=self.precharge_cell,
                                         offset=offset)
                    bl_name = "bl[{0}]".format(i)
                    br_name = "br[{0}]".format(i)
                    self.copy_layout_pin(inst, "bl", bl_name)
                    self.copy_layout_pin(inst, "br", br_name)

                    self.connect_inst([bl_name, br_name, "en", "vdd", "gnd"])

                self.width = self.insts[-1].rx()
                self.height = self.insts[0].height

                # Add vdd/gnd labels at the right edge so no degradation at the relevant cell
                # which is the rightmost precharge cell
                # en label should be on the left
                label_x_offsets = [0, self.width, self.width]
                pin_names = ["en", "vdd", "gnd"]
                for i in range(3):
                    cell_pin = self.precharge_cell.get_pin(pin_names[i])
                    self.add_rect(cell_pin.layer, offset=vector(0, cell_pin.by()),
                                  width=self.width, height=cell_pin.height())
                    # add min width pin
                    self.add_layout_pin(pin_names[i], layer=cell_pin.layer,
                                        offset=vector(label_x_offsets[i], cell_pin.by()),
                                        height=cell_pin.height())

                # fill gaps
                inv_fill = create_wells_and_implants_fills(self.precharge_cell.inv,
                                                           self.precharge_cell.inv)

                # extend NWELL
                nwell_width = self.width + (self.precharge_cell.precharge.implant_width -
                                            bitcell.width)

                for layer, bottom, top, _, _ in inv_fill:
                    width = nwell_width if layer == NWELL else self.width
                    self.add_rect(layer, offset=vector(0, bottom),
                                  width=width, height=top - bottom)

                precharge_fill = create_wells_and_implants_fills(self.precharge_cell.precharge,
                                                                 self.precharge_cell.precharge)
                for layer, bottom, top, _, _ in precharge_fill:
                    width = nwell_width if layer == NWELL else self.width
                    y_offset = (self.precharge_cell.precharge_inst.by() +
                                self.precharge_cell.precharge.height - top)
                    self.add_rect(layer, offset=vector(0, y_offset),
                                  width=width, height=top - bottom)

            def add_pins(self):
                pins = []
                for i in range(self.columns):
                    pins.extend(["bl[{}]".format(i), "br[{}]".format(i)])
                pins.extend(["en", "gnd", "vdd"])
                self.add_pin_list(pins)

        class PrechargeDut(design):
            def __init__(self):
                self.name = "precharge_dut_{}_{:.4g}".format(num_elements, precharge_size)
                self.name = self.name.replace(".", "__")
                super().__init__(self.name)
                self.num_elements = num_elements
                self.precharge_size = precharge_size
                self.create_layout()

            def create_layout(self):
                self.add_pins()

                # Buffer stages
                min_tx_width = drc["minwidth_tx"]
                buffer_stages_sizes = [1e6 * x / min_tx_width for x in buffer_stages]
                buffer = BufferStage(buffer_stages_sizes, height=OPTS.logic_buffers_height,
                                     contact_pwell=True, contact_nwell=True,
                                     route_outputs=False)
                self.add_mod(buffer)
                wire_length = max(test_class_self.options.driver_wire_length or 0.0,
                                  3 * buffer.width)
                self.buffer_inst = self.add_inst("buffer", mod=buffer,
                                                 offset=vector(0, 0))
                self.connect_inst(["in", "en", "en_bar", "vdd_buffer", "gnd"])
                self.copy_layout_pin(self.buffer_inst, "vdd", "vdd_buffer")
                self.copy_layout_pin(self.buffer_inst, "gnd", "gnd")
                self.copy_layout_pin(self.buffer_inst, "in", "in")

                # temporary add second buffer as load to
                # self.add_inst("temp_en_buf", mod=buffer.buffer_invs[0],
                #               offset=self.buffer_inst.ul() + vector(0, buffer.height))
                # self.connect_inst(["en_bar", "en_buf", "vdd", "gnd"])

                # Precharge Array
                x_offset = self.buffer_inst.rx() + wire_length
                self.precharge_array = PrechargeArray()
                self.add_mod(self.precharge_array)

                self.precharge_array_inst = self.add_inst("precharge_array",
                                                          mod=self.precharge_array,
                                                          offset=vector(x_offset, 0))
                terminals = []
                for i in range(self.num_elements):
                    terminals.extend(["bl[{}]".format(i), "br[{}]".format(i)])
                terminals.extend(["en", "gnd", "vdd_precharge"])
                self.connect_inst(terminals)

                self.copy_layout_pin(self.precharge_array_inst, "vdd", "vdd_precharge")
                self.copy_layout_pin(self.precharge_array_inst, "gnd", "gnd")

                # connect buffer and precharge gnd, en
                buffer_names = ["gnd", "out_inv"]
                precharge_names = ["gnd", "en"]
                for i in range(2):
                    buffer_pin = self.buffer_inst.get_pin(buffer_names[i])
                    precharge_pin = self.precharge_array_inst.get_pin(precharge_names[i])
                    if i == 0:
                        height = buffer_pin.height()
                    else:
                        self.add_rect(METAL2, offset=precharge_pin.ul(),
                                      height=buffer_pin.by() + self.m2_width - precharge_pin.uy())
                        via_y = buffer_pin.by() + m1m2.width - m1m2.height
                        self.add_contact(m1m2.layer_stack, offset=vector(precharge_pin.lx(),
                                                                         via_y))
                        height = self.get_min_layer_width(buffer_pin.layer)
                    self.add_rect(buffer_pin.layer, offset=buffer_pin.lr(),
                                  width=precharge_pin.lx() - buffer_pin.rx(),
                                  height=height)

                # Bitcell array
                bitcell_arr = bitcell_array(cols=1, rows=num_elements)
                self.add_mod(bitcell_arr)
                precharge_bl = self.precharge_array_inst.get_pin("bl[{}]".format(num_elements - 1))
                bitcell_bl = bitcell_arr.get_pin("bl[0]")
                x_offset = precharge_bl.lx() - bitcell_bl.lx()

                top_bitcell_y = bitcell.get_nwell_top()
                nwell_space = drc["different_line_space_nwell"]
                y_offset = (self.precharge_array_inst.uy() + (top_bitcell_y - bitcell.height) +
                            nwell_space)
                bitcell_array_inst = self.add_inst("bitcell_array", bitcell_arr,
                                                   offset=vector(x_offset, y_offset))
                terminals = ["bl[{}]".format(num_elements - 1), "br[{}]".format(num_elements - 1)]

                for i in range(num_elements):
                    terminals.append("wl[{}]".format(i))
                terminals.extend(["vdd_bitcell", "gnd"])
                self.connect_inst(terminals)

                # connect lowest bitcell gnd with precharge gnd
                bitcell_gnds = bitcell_array_inst.get_pins("gnd")
                bottom_gnd = min(filter(lambda x: x.layer == METAL1, bitcell_gnds),
                                 key=lambda x: x.by())
                precharge_gnd = self.precharge_array_inst.get_pin("gnd")
                extension = bitcell.width
                x_offset = precharge_gnd.rx() + extension
                self.add_rect(METAL1, offset=precharge_gnd.lr(), height=precharge_gnd.height(),
                              width=extension)
                self.add_rect(METAL1, offset=bottom_gnd.lr(), width=x_offset - bottom_gnd.rx(),
                              height=bottom_gnd.height())
                self.add_rect(METAL1, offset=vector(x_offset, precharge_gnd.by()),
                              width=precharge_gnd.height(),
                              height=bottom_gnd.uy() - precharge_gnd.by())

                for pin_name in ["bl", "br"]:
                    bitcell_pin = bitcell_array_inst.get_pin("{}[0]".format(pin_name))
                    precharge_pin = self.precharge_array_inst.get_pin("{}[{}]".
                                                                      format(pin_name,
                                                                             num_elements - 1))
                    self.add_rect(precharge_pin.layer, offset=precharge_pin.ul(),
                                  width=precharge_pin.width(),
                                  height=bitcell_pin.by() - precharge_pin.uy())

                self.copy_layout_pin(bitcell_array_inst, "vdd", "vdd_bitcell")
                self.copy_layout_pin(bitcell_array_inst, "gnd", "gnd")

                for i in range(num_elements):
                    self.copy_layout_pin(bitcell_array_inst, "wl[{}]".format(i))

            def add_pins(self):
                self.add_pin_list(["in", "vdd_precharge", "vdd_buffer",
                                   "vdd_bitcell", "gnd"])
                for i in range(num_elements):
                    self.add_pin("wl[{}]".format(i))

        dut = PrechargeDut()
        return dut


NVSimComparison.run_tests(__name__)
