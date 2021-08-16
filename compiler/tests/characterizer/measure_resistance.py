#!/usr/bin/env python3
import json
import numpy as np
import os
import pathlib
from importlib import reload

import matplotlib.pyplot as plt

from char_test_base import CharTestBase
from characterization_utils import (TEN_FIFTY_THRESH, TEN_NINETY,
                                    get_measurement_threshold,
                                    get_scale_factor,
                                    search_meas,
                                    replace_arg)

ACTION_SINGLE = "single"  # run single simulation using default technology beta, print r_p, r_n
ACTION_SWEEP = "sweep"  # for each gate (pinv, pnand2/3, pnor2, and sizes from size->max_size, sweep
ACTION_SWEEP_TX = "sweep_tx"  # sweep but for transistors
ACTION_BETA_SWEEP = "beta_sweep"  # sweep beta from 'min_beta' to 'max_beta' and save r_p, r_n
ACTION_BETA_PLOT = "beta_plot"  # plot previous beta sweep

MOS = "mos"
NMOS = "nmos"
PMOS = "pmos"

DEFAULT_PERIOD = 2e-9


class MeasureResistance(CharTestBase):
    buffer_stages = [1, 1, 4]

    @classmethod
    def add_additional_options(cls):
        from pgates_caps import PINV, PNAND2, PNOR2, PNAND3

        replace_arg(cls.parser, "period", default=DEFAULT_PERIOD, arg_type=float)
        cls.parser.add_argument("--gate", default=PINV,
                                choices=[PINV, PNAND2, PNAND3, PNOR2, MOS])
        cls.parser.add_argument("-l", "--load", default=30e-15, type=float)
        cls.parser.add_argument("-m", "--method", default=TEN_FIFTY_THRESH,
                                choices=[TEN_NINETY, TEN_FIFTY_THRESH])
        cls.parser.add_argument("-a", "--action", default=ACTION_SWEEP,
                                choices=[ACTION_SINGLE, ACTION_SWEEP, ACTION_SWEEP_TX,
                                         ACTION_BETA_SWEEP, ACTION_BETA_PLOT])
        cls.parser.add_argument("-s", "--size",
                                default=1, type=float, help="Inverter size")
        cls.parser.add_argument("--max_size",
                                default=50, type=float, help="Inverter size")
        cls.parser.add_argument("--num_sizes",
                                default=10, type=float, help="Inverter size")
        cls.parser.add_argument("--min_beta", type=float, default=1.0, help="min beta for beta sweep")
        cls.parser.add_argument("--max_beta", type=float, default=3.0, help="max beta for beta sweep")

    def add_additional_includes(self, stim_file):
        if self.dut_pex:
            if isinstance(self.dut_pex, str):
                dut_pex = [self.dut_pex]
            else:
                dut_pex = self.dut_pex
            for f in dut_pex:
                stim_file.write(".include \"{0}\" \n".format(f))

    def run_simulation(self):
        """
        Measure resistance using a large (much larger than Cds/Cdb)
         CLoad such that the delay is essentially R*Cload
         Rise/Fall times should be 2.2*Rp.Cload / 2.2*Rn.Cload for 10%-90%
        """
        import characterizer

        from modules.buffer_stage import BufferStage
        from pgates_caps import PINV
        from pgates_caps import PgateCaps
        from characterizer.stimuli import stimuli
        from tx_capacitance import TxCapacitance
        from pgates.ptx import ptx

        reload(characterizer)

        gate = self.options.gate
        size = self.options.size

        sim_dir = "beta_{:.3g}".format(self.options.beta)
        self.set_temp_folder(sim_dir)

        if gate == PINV:
            # crude logical effort
            buffer_stages = [(size ** (1 / 3)) ** (x + 1) for x in range(3)]
        else:
            buffer_stages = self.buffer_stages

        buffer = BufferStage(buffer_stages=buffer_stages,
                             height=self.logic_buffers_height)

        buffer_pex = self.run_pex_extraction(buffer, buffer.name, run_drc=self.options.run_drc_lvs,
                                             run_lvs=self.options.run_drc_lvs)

        vdd_value = self.corner[1]

        rise_start, rise_end, fall_start, fall_end = get_measurement_threshold(
            self.options.method, vdd_value)

        if gate == PINV:
            dut_instance = "X1 a out_bar out vdd gnd        {}".format(buffer.name)
            self.dut_pex = None
        elif gate == MOS:
            self.options.tx_type = NMOS
            n_tx = ptx(width=self.options.tx_width, mults=self.options.num_fingers,
                       tx_type=NMOS, connect_active=True, connect_poly=True)
            nmos_wrapped = TxCapacitance.create_mos_wrapper(self.options, beta_suffix=False)(n_tx)

            self.options.tx_type = PMOS
            p_tx = ptx(width=self.options.tx_width, mults=self.options.num_fingers,
                       tx_type=PMOS, connect_active=True, connect_poly=True)
            pmos_wrapped = TxCapacitance.create_mos_wrapper(self.options, beta_suffix=False)(p_tx)

            nmos_pex = self.run_pex_extraction(nmos_wrapped, nmos_wrapped.name)
            pmos_pex = self.run_pex_extraction(pmos_wrapped, pmos_wrapped.name)
            self.dut_pex = [nmos_pex, pmos_pex]

            dut_instance = "X1 a d out vdd gnd        {}\n".format(buffer.name)

            # add nmos
            dut_instance += "Xnmos out_bar d gnd gnd {} \n".format(nmos_wrapped.name)
            dut_instance += "Xpmos out_bar d vdd vdd {} \n".format(pmos_wrapped.name)
        else:
            # add buffer stages to shape the input slew, "d" is the equivalent "out_bar"
            dut_instance = "X1 a d out vdd gnd        {}".format(buffer.name)
            pin_name = "A"  # A pin is always farthest from output
            mod, module_args, terminals = PgateCaps.get_pgate_params(gate, pin_name, size,
                                                                     height=self.logic_buffers_height,
                                                                     options=self.options)
            # pgate output is always third to the last
            dut = mod(**module_args)
            self.dut_pex = self.run_pex_extraction(dut, dut.name)

            terminals[-3] = "out_bar"
            connections = " ".join(terminals)
            dut_instance += "\nX4 {connections}    {dut_name} \n".format(
                connections=connections, dut_name=dut.name)

        c_load = size * self.options.load
        period = self.options.period * size

        args = {
            "dut_instance": dut_instance,
            "buffer_name": buffer.name,
            "vdd_value": vdd_value,
            "PERIOD": period,
            "TEMPERATURE": self.corner[2],
            "half_vdd": 0.5 * vdd_value,
            "meas_delay": "0.3n",
            "Cload": c_load,
            "rise_start": rise_start,
            "rise_end": rise_end,
            "fall_start": fall_start,
            "fall_end": fall_end
        }

        spice_content = spice_template.format(**args)

        self.stim_file_name = self.prefix("stim.sp")

        with open(self.stim_file_name, "w") as stim_file:
            stim_file.write("simulator lang=spice \n")
            stim = stimuli(stim_file, corner=self.corner)
            stim.write_include(buffer_pex)
            self.add_additional_includes(stim_file)
            stim_file.write(spice_content)

        stim.run_sim()

        meas_file = self.prefix("stim.measure")
        fall_time = float(search_meas("fall_time", meas_file))
        rise_time = float(search_meas("rise_time", meas_file))

        scale_factor = get_scale_factor(self.options.method)

        r_n = fall_time / (scale_factor * c_load) * size
        r_p = rise_time / (scale_factor * c_load) * size

        return r_n, r_p, fall_time, rise_time, scale_factor

    def plot_sim(self):
        from characterizer.simulation.psf_reader import PsfReader

        sim_dir = "beta_{:.3g}".format(self.options.beta)
        self.set_temp_folder(sim_dir)

        sim_tran = self.prefix("timeSweep.tran.tran")
        sim_data = PsfReader(sim_tran)
        time = sim_data.time
        out_data = sim_data.get_signal('out_bar')
        plt.plot(time, out_data, label="out_bar")

        plt.plot(time, sim_data.get_signal('a'), label="input")
        plt.grid()
        plt.legend()
        plt.tight_layout()
        plt.show()

    def test_single_sim(self):

        import debug

        if not self.options.action == ACTION_SINGLE:
            return
        r_n, r_p, fall_time, rise_time, scale_factor = self.run_simulation()
        debug.info(0, "Scale factor = {:.4g}".format(scale_factor))
        debug.info(0, "Rise time = {:.4g}".format(rise_time))
        debug.info(0, "Fall time = {:.4g}".format(fall_time))
        debug.info(0, "NMOS resistance = {:.4g}".format(r_n))
        debug.info(0, "PMOS resistance = {:.4g}".format(r_p))
        if self.options.plot:
            self.plot_sim()

    def test_sweep_tx(self):
        if not self.options.action == ACTION_SWEEP_TX:
            return
        from tech import drc
        self.options.gate = MOS

        for num_fingers in [1, 2, 3, 4, 5, 6, 10, 20, 40]:
            print("  fingers: {}".format(num_fingers))
            self.options.num_fingers = num_fingers
            max_log = np.log10(10)
            sizes = [1, 1.25, 1.5, 1.75, 2, 2.5, 3, 5, 10]
            for size in sizes:
                self.options.size = size
                self.options.tx_width = size * drc["minwidth_tx"]
                r_n, r_p, _, _, _ = self.run_simulation()
                resistances = [r_n, r_p]
                gates = [NMOS, PMOS]
                for ii in range(2):
                    resistance = resistances[ii]
                    resistance = resistance * drc["minwidth_tx"] * num_fingers

                    print("    {} size: {:.3g}: {:.6g}".format(gates[ii], size, resistance))
                    size_suffixes = [("nf", num_fingers)]
                    self.save_result(gates[ii], "resistance", resistance, size=size,
                                     size_suffixes=size_suffixes,
                                     file_suffixes=[])

    def test_sweep(self):
        from pgates_caps import PINV, PNAND2, PNOR2, PNAND3
        if not self.options.action == ACTION_SWEEP:
            return

        initial_size = self.options.size

        for gate in [PNAND2, PNOR2, PNAND3, PINV]:
            print("\n{}:".format(gate.upper()))
            if gate == PINV:
                max_log = np.log10(self.options.max_size)
                sizes = np.logspace(0, max_log, self.options.num_sizes)
            else:
                sizes = [initial_size, 1.5, 2]
            for size in sizes:
                print("  size: {:.3g}:".format(size))
                self.options.gate = gate
                self.options.size = size
                try:
                    r_n, r_p, fall_time, rise_time, scale_factor = self.run_simulation()
                except AssertionError as ex:
                    if len(ex.args) > 0 and "Only Single finger" in ex.args[0]:
                        print("    Invalid size {} for {}".format(size, gate))
                        continue
                    raise ex

                file_suffixes = [("beta", self.options.beta)]
                if not self.options.horizontal:
                    file_suffixes.append(("contacts", int(not self.options.no_contacts)))
                size_suffixes = [("height", self.logic_buffers_height)]

                print("    Rn = {:.4g}".format(r_n))
                print("    Rp = {:.4g}".format(r_p))

                pin_names = ["r_n", "r_p", "resistance"]
                values = [r_n, r_p, max(r_n, r_p)]
                for i in range(3):
                    self.save_result(gate, pin_names[i], values[i], size=size,
                                     size_suffixes=size_suffixes,
                                     file_suffixes=file_suffixes)

    def test_beta_sweep(self):
        from globals import OPTS
        from base.design import design
        from pgates.pinv import pinv
        from modules.buffer_stage import BufferStage

        if not self.options.action == ACTION_BETA_SWEEP:
            return

        results_dir = OPTS.openram_temp

        all_beta = np.linspace(self.options.min_beta, self.options.max_beta, self.options.num_sizes)
        methods = [TEN_FIFTY_THRESH, TEN_NINETY]

        results = {
            "Rn": {},
            "Rp": {}
        }

        for i in range(len(methods)):
            self.options.method = methods[i]
            method_r_n = []
            method_r_p = []
            print("\n{}\n".format(methods[i].upper()))
            for j in range(len(all_beta)):
                self.options.beta = all_beta[j]
                print("  beta: {:.3g}:".format(self.options.beta))

                # clear existing designs
                self.set_beta(self.options)
                design.name_map.clear()
                pinv._cache.clear()
                BufferStage._cache.clear()

                r_n, r_p, _, _, _ = self.run_simulation()
                method_r_n.append(r_n)
                method_r_p.append(r_p)
                print("    Rn = {:.4g}".format(r_n))
                print("    Rp = {:.4g}".format(r_p))
            results["Rn"][self.options.method] = [all_beta.tolist(), method_r_n]
            results["Rp"][self.options.method] = [all_beta.tolist(), method_r_p]

        results_file_name = os.path.join(results_dir,
                                         "{}_resistance_beta.json".format(self.options.gate))

        if not os.path.exists(results_dir):
            pathlib.Path(results_dir).mkdir(parents=True, exist_ok=True)

        with open(results_file_name, "w") as results_file:
            json.dump(results, results_file, indent=4)

    def test_plot(self):

        from globals import OPTS

        if not self.options.action == ACTION_BETA_PLOT:
            return

        results_dir = OPTS.openram_temp
        results_file_name = os.path.join(results_dir,
                                         "{}_resistance_beta.json".format(self.options.gate))

        with open(results_file_name, "r") as results_file:
            results = json.load(results_file)

        fig, subplots = plt.subplots(nrows=1, ncols=2, sharey=True)

        plot_keys = ["Rp", "Rn"]

        methods = [TEN_FIFTY_THRESH, TEN_NINETY]

        for i in range(2):
            plot_key = plot_keys[i]
            for j in range(2):
                method = methods[j]
                data = results[plot_key][method]
                subplots[i].plot(data[0], data[1], "-o", label=method)

            subplots[i].set_title(plot_key)
            subplots[i].set_xlabel(r"$\beta$")
            subplots[i].set_ylabel(r"Resistance ($\Omega$)")
            subplots[i].legend()
            subplots[i].grid()

        fig.tight_layout()
        plt.savefig(os.path.join(results_dir, "resistances.png"))
        plt.savefig(os.path.join(results_dir, "resistances.pdf"))
        plt.show()


spice_template = """
.PARAM PERIOD={PERIOD}
Vgnd gnd 0 0
Vdd vdd gnd {vdd_value}
Vin a gnd pulse 0 {vdd_value} 0ps 20ps 20ps '0.5*PERIOD' 'PERIOD'
{dut_instance}
cdelay out_bar gnd '{Cload}'                        * linear capacitance

.measure rise_time TRIG v(out_bar) VAL='{rise_start}' RISE=1 TARG v(out_bar) VAL='{rise_end}' RISE=1
.measure fall_time TRIG v(out_bar) VAL='{fall_start}' FALL=1 TARG v(out_bar) VAL='{fall_end}' FALL=1

.tran 1ps '2*{PERIOD}'

simulator lang=spectre
dcOp dc write="spectre.dc" readns="spectre.dc" maxiters=150 maxsteps=10000 annotate=status
saveOptions options save=lvlpub nestlvl=1 pwr=total
simulatorOptions options temp={TEMPERATURE} maxnotes=10 maxwarns=10  preservenode=all topcheck=fixall dc_pivot_check=yes

"""

MeasureResistance.run_tests(__name__)
