#!/usr/bin/env python3
import argparse
import os
import pathlib
from importlib import reload

import numpy as np

from char_test_base import CharTestBase
from characterization_utils import parse_options

ACTION_SINGLE = "single"
ACTION_HEIGHT_SWEEP = "height_sweep"
ACTION_BETA_SWEEP = "beta_sweep"

parser = argparse.ArgumentParser()
parser.add_argument("-B", "--beta", default=None, type=float)
parser.add_argument("--min_beta", default=None, type=float)
parser.add_argument("--max_beta", default=None, type=float)
parser.add_argument("-p", "--plot", action="store_true")
parser.add_argument("--height", default=None, type=float)

parser.add_argument("-a", "--action", default=ACTION_SINGLE,
                    choices=[ACTION_SINGLE, ACTION_HEIGHT_SWEEP, ACTION_BETA_SWEEP])
parser.add_argument("--run_drc_lvs", action="store_true")

options = parse_options(parser)


class FO4DelayCharacterizer(CharTestBase):

    def test_height_sweep(self):

        if (not options.action == ACTION_HEIGHT_SWEEP) or options.plot:
            return
        scale_factors = [0.8, 0.9, 1, 1.1, 1.2]
        module_heights = [self.logic_buffers_height * x for x in scale_factors]

        results = []

        print("{:<12}\t{:<12}\t{:<12}".format("Height", "Rise (ps)", "Fall (ps)"))

        for module_height in module_heights:
            rise_time, fall_time = self.run_sim(module_height)
            results.append((module_height, fall_time, rise_time))
            print("{:<12.3g}\t{:<12.3g}\t{:<12.3g}".format(module_height,
                                                           float(rise_time) * 1e12,
                                                           float(fall_time) * 1e12))

        self.save_data(results, f"height_sweep_beta_{self.options.beta}")

    def save_data(self, results, prefix):
        results_dir = self.get_char_data_file(os.path.join("FO4"))
        if not os.path.exists(results_dir):
            pathlib.Path(results_dir).mkdir(parents=True, exist_ok=True)

        results_file_name = os.path.join(results_dir, prefix + ".txt")
        with open(results_file_name, "w") as results_file:
            for module_height, fall_time, rise_time in results:
                results_file.write("{:.4g}, {}, {} \n".
                                   format(module_height, rise_time, fall_time))

    def test_beta_sweep(self):
        if not options.action == ACTION_BETA_SWEEP or options.plot:
            return
        from globals import OPTS
        from tech import parameter
        min_beta = options.min_beta or 1.0
        max_beta = options.max_beta or parameter["beta"]
        all_beta = np.linspace(min_beta, max_beta, 10)
        results = []
        height = options.height or OPTS.logic_buffers_height
        for beta in all_beta:
            options.beta = beta
            rise_time, fall_time = self.run_sim(height)
            results.append((beta, fall_time, rise_time))
            print("beta = {:<12.3g}\t{:<12.3g}\t{:<12.3g}".format(beta,
                                                                  float(rise_time) * 1e12,
                                                                  float(fall_time) * 1e12))
            self.save_data(results, f"beta_sweep_h_{height:.3g}")

    def test_single_sim(self):
        from globals import OPTS
        import debug
        if (not options.action == ACTION_SINGLE) or options.plot:
            return
        height = options.height or OPTS.logic_buffers_height
        rise_time, fall_time = self.run_sim(height)
        debug.info(0, "Rise time = {:.3g}ps".format(rise_time * 1e12))
        debug.info(0, "Fall time = {:.3g}ps".format(fall_time * 1e12))

    def run_sim(self, module_height):
        if options.plot:
            return
        from globals import OPTS
        from modules.buffer_stage import BufferStage

        import characterizer
        from characterizer import stimuli
        reload(characterizer)

        self.set_beta(options)

        beta_dir = "beta_{:.3g}".format(options.beta)

        OPTS.openram_temp = os.path.join(CharTestBase.temp_folder, beta_dir)

        if not os.path.exists(OPTS.openram_temp):
            pathlib.Path(OPTS.openram_temp).mkdir(parents=True, exist_ok=True)

        OPTS.check_lvsdrc = self.run_drc_lvs = options.run_drc_lvs

        driver_sizes = [1, 4, 16, 64, 128]

        pex_files = [None] * len(driver_sizes)
        drivers = [None] * len(driver_sizes)
        for i in range(len(driver_sizes)):
            driver_size = driver_sizes[i]
            driver = BufferStage(buffer_stages=[driver_size], height=module_height,
                                 route_outputs=False)
            drivers[i] = driver

            pex_file = self.prefix("{}.pex.sp".format(driver.name))
            if not os.path.exists(pex_file) or self.options.force_pex:
                self.run_pex_extraction(driver, driver.name, run_drc=False)
            pex_files[i] = pex_file

        sim_dir = os.path.join(OPTS.openram_temp, "h{:.4g}".format(module_height))
        OPTS.openram_temp = sim_dir
        if not os.path.exists(OPTS.openram_temp):
            pathlib.Path(OPTS.openram_temp).mkdir(parents=True, exist_ok=True)
        stim_file_name = os.path.join(sim_dir, "stim.sp")

        with open(stim_file_name, "w") as stim_file:

            stim = stimuli(stim_file, corner=self.corner)
            stim_file.write("\n")  # first line should be a comment or empty

            stim.write_include(pex_files[0])
            for pex_file in pex_files[1:]:
                stim.sf.write(".include \"{0}\"\n".format(pex_file))

            # add buffer stages
            node_names = ["vin", "out_1", "fo4_in", "fo4_out", "out_64", "out_final"]
            for i in range(5):
                max_j = 1 if i < 4 else 2  # double for last load
                for j in range(max_j):
                    stim_file.write("Xbuf{0} {1} {2} dummy{0} vdd gnd {3}\n".format(
                        i + j, node_names[i], node_names[i + 1], drivers[i].name
                    ))

            # Add stimulus
            vdd_value = self.corner[1]
            sim_params = {
                "PERIOD": self.options.period,
                "vdd_value": vdd_value,
                "half_vdd": 0.5 * vdd_value,
            }
            stim_file.write(stimulus_template.format(**sim_params))
            stim.write_supply()
            stim.write_control(end_time=1.45 * self.options.period * 1e9)

        stim.run_sim()

        from characterizer.charutils import parse_output
        fall_time = parse_output(None, key="fall_time", sim_dir=OPTS.openram_temp)
        rise_time = parse_output(None, key="rise_time", sim_dir=OPTS.openram_temp)
        return rise_time, fall_time

    def test_plot(self):
        if not options.plot:
            return
        results_dir = self.get_char_data_file(os.path.join("FO4"))
        rise_times = []
        fall_times = []
        for f in os.listdir(results_dir):
            if not f.startswith("beta"):
                continue
            beta = float(f[5:-4])
            res_fall_times = []
            res_rise_times = []
            with open(os.path.join(results_dir, f), "r") as result_file:
                for line in result_file.readlines():
                    if not line.strip():
                        break
                    module_height, rise_time, fall_time = line.split(",")
                    res_rise_times.append([float(module_height), float(rise_time)])
                    res_fall_times.append([float(module_height), float(fall_time)])
            rise_times.append((beta, res_rise_times))
            fall_times.append((beta, res_fall_times))

        import numpy as np
        from matplotlib import pyplot as plt
        fig, subplots = plt.subplots(nrows=1, ncols=2, sharey=True)

        data_sources = [rise_times, fall_times]
        titles = ["Rise times", "Fall times"]
        for i in range(2):
            sorted_data = list(sorted(data_sources[i], key=lambda x: x[0]))
            for beta, data in sorted_data:
                data = np.array(data)
                subplots[i].plot(data[:, 0], data[:, 1] * 1e12, label="beta={:.3g}".format(beta))
            subplots[i].set_title(titles[i])
            subplots[i].set_xlabel("Cell height ($\mu m$)")
            subplots[i].set_ylabel("Time (ps)")
            subplots[i].legend()
            subplots[i].grid()
        fig.tight_layout()
        plt.savefig(os.path.join(results_dir, "fo4_delays.png"))
        plt.savefig(os.path.join(results_dir, "fo4_delays.pdf"))

        plt.show()




stimulus_template = """
Vin vin gnd pulse ({vdd_value} 0 -2ps 2ps 2ps '0.5*{PERIOD}' '{PERIOD}')
.measure rise_time TRIG v(fo4_in) VAL='{half_vdd}' FALL=1 TARG v(fo4_out) VAL='{half_vdd}' RISE=1
.measure fall_time TRIG v(fo4_in) VAL='{half_vdd}' RISE=1 TARG v(fo4_out) VAL='{half_vdd}' FALL=1
"""

FO4DelayCharacterizer.run_tests(__name__)
