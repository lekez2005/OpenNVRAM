import argparse
import inspect
import json
import os
import pathlib
import re
import sys
import unittest
from importlib import reload
from typing import List, Tuple, Union

import numpy as np

from characterization_utils import parse_options

sys.path.append('..')

import testutils


def parallel_sim(command_iterator, max_jobs=50, nice=15, **subprocess_params):
    import psutil
    import time
    import subprocess

    def preexec_fn():
        pid = os.getpid()
        ps = psutil.Process(pid)
        ps.nice(nice)

    processes = set()
    for command in command_iterator:
        processes.add(subprocess.Popen(command, preexec_fn=preexec_fn, **subprocess_params))
        time.sleep(0.1)

        if len(processes) >= max_jobs:
            os.wait()
            processes.difference_update([
                p for p in processes if p.poll() is not None])

    # ensure all done
    while len(processes) > 0:
        os.wait()
        processes.difference_update([
            p for p in processes if p.poll() is not None])


class CharTestBase(testutils.OpenRamTest):
    config_template = os.path.dirname(os.path.dirname(__file__)) + "/config_20_{}"
    spice_template = "cin_template.sp"
    run_pex = True
    instantiate_dummy = False
    buffer_stages = [1, 4]

    parser = None  # type: argparse.ArgumentParser

    default_cols = [8, 16, 32, 64, 128, 256]
    driver_size = 8
    use_mdl = False

    @classmethod
    # use cls so we can override class methods
    # Always call this with child class if overriding class methods
    def run_tests(cls, name):
        if name == "__main__":
            cls.parse_custom_options()
            testutils.parse_args()
            unittest.main()

    @classmethod
    def parse_custom_options(cls):
        cls.parser = parser = argparse.ArgumentParser()
        parser.add_argument("-B", "--beta", default=None, type=float)
        parser.add_argument("--height", default=None, type=float)

        parser.add_argument("--driver_stages", default=None)
        parser.add_argument("--driver_wire_length", default=None, type=float)

        parser.add_argument("--cell_mod", default=None)
        parser.add_argument("--body_tap", default=None)
        parser.add_argument("--no_contacts", action="store_true")
        parser.add_argument("--horizontal", action="store_true")

        parser.add_argument("--min_c", default=0.1e-15, type=float)
        parser.add_argument("--max_c", default=20e-15, type=float)
        parser.add_argument("--period", default=1e-9, type=float)

        parser.add_argument("--run_drc_lvs", action="store_true")
        parser.add_argument("--force_pex", action="store_true")
        # for some reason, mdl isn't as accurate, may need to investigate tolerances
        parser.add_argument("--use_mdl", action="store_true")
        parser.add_argument("--no_save", action="store_true")

        parser.add_argument("--max_iterations", default=30, type=int)
        parser.add_argument("--spice_name", default="spectre")

        parser.add_argument("-p", "--plot", action="store_true")
        parser.add_argument("--scale_by_x", action="store_true")
        parser.add_argument("--save_plot", action="store_true")

        parser.add_argument("--subprocess_nice", default=15, type=int)

        cls.add_additional_options()

        cls.options = options = parse_options(parser)

        os.environ["OPENRAM_SUBPROCESS_NICE"] = str(options.subprocess_nice)

        options.start_c = 0.5 * (options.max_c + options.min_c)
        cls.run_pex = options.force_pex
        cls.run_drc_lvs = cls.options.run_drc_lvs

    @classmethod
    def add_additional_options(cls):
        pass

    def setUp(self):

        super().setUp()

        from globals import OPTS

        self.logic_buffers_height = OPTS.logic_buffers_height

        OPTS.check_lvsdrc = False

        OPTS.analytical_delay = False
        OPTS.spice_name = self.options.spice_name
        OPTS.spectre_command_options = " +aps +mt=16 "

        self.set_beta(self.options)

        if self.options.driver_stages is not None:
            self.buffer_stages = [float(x) for x in
                                  self.options.driver_stages.split(",")]

        self.driver_wire_length = self.options.driver_wire_length

    @staticmethod
    def prefix(filename):
        from globals import OPTS
        return os.path.join(OPTS.openram_temp, filename)

    @staticmethod
    def get_char_data_file(file_name):
        from globals import OPTS
        return os.path.join(OPTS.openram_tech, "char_data", file_name)

    @staticmethod
    def set_beta(options):
        from tech import parameter
        if options.beta is None:
            options.beta = parameter["beta"]
        else:
            parameter["beta"] = options.beta

    @staticmethod
    def set_temp_folder(dir_name):
        from globals import OPTS
        openram_temp_ = os.path.join(CharTestBase.temp_folder, dir_name)
        if openram_temp_ == OPTS.openram_temp:
            return
        OPTS.openram_temp = openram_temp_
        if not os.path.exists(OPTS.openram_temp):
            pathlib.Path(OPTS.openram_temp).mkdir(parents=True, exist_ok=True)
        print("\n Temp folder = {}".format(OPTS.openram_temp))

    def run_pex_extraction(self, module, name_prefix, run_drc=False, run_lvs=False):
        import verify

        spice_file = self.prefix("{}.sp".format(name_prefix))
        gds_file = self.prefix("{}.gds".format(name_prefix))
        pex_file = self.prefix("{}.pex.sp".format(name_prefix))

        run_pex = self.run_pex or not os.path.exists(pex_file)

        if run_pex or run_lvs or run_drc:
            module.sp_write(spice_file)
            module.gds_write(gds_file)
        if run_drc:
            verify.run_drc(module.name, gds_file)
        if run_lvs:
            verify.run_lvs(module.name, gds_file, spice_file, final_verification=False)
        if run_pex:
            errors = verify.run_pex(module.name, gds_file, spice_file, pex_file,
                                    run_drc_lvs=self.run_drc_lvs)
            if errors:
                raise AssertionError("PEX failed for {}".format(name_prefix))
        return pex_file

    @staticmethod
    def dummy_driver(args):
        template = """
Vin_dummy a_dummy gnd pulse {vdd_value} 0 0ps 20ps 20ps '0.5*PERIOD' 'PERIOD'
X1_dummy a_dummy b_dummy c_dummy vdd gnd        {in_buffer_name}    * set appropriate slope
X3_dummy c_dummy d_dummy d_bar_dummy vdd gnd    {driver_name}       * drive real load
X6_dummy c_dummy g_dummy g_bar_dummy vdd gnd    {driver_name}       * drive linear capacitor
cdelay_dummy g_dummy gnd 'Cload'                                          * linear capacitor
        """
        return template.format(**args)

    @staticmethod
    def generate_mdl(args):
        template = """
// more info at mdlref.pdf
alias measurement trans {{
    run tran( stop=2*{PERIOD}, autostop='yes)
    export real loadRise=cross(sig=V(d), dir='rise, n=1, thresh={half_vdd}) \\
        -  cross(sig=V(c), dir='fall, n=1, thresh={half_vdd})
    export real loadFall=cross(sig=V(d), dir='fall, n=1, thresh={half_vdd}) \\
        -  cross(sig=V(c), dir='rise, n=1, thresh={half_vdd})
    export real capRise=cross(sig=V(g), dir='rise, n=1, thresh={half_vdd}) \\
        -  cross(sig=V(c), dir='fall, n=1, thresh={half_vdd})
    export real capFall=cross(sig=V(g), dir='fall, n=1, thresh={half_vdd}) \\
        -  cross(sig=V(c), dir='rise, n=1, thresh={half_vdd})
}}

mvarsearch {{
    option {{
        method = 'lm  // can be 'newton
        accuracy = 1e-3 // convergence tolerance
        // deltax = 1e-5 // numerical difference % of design variables
        maxiter = {max_iterations} // limit to {max_iterations} iterations
    }}
    parameter {{
        {{ Cload, {start_c}, {min_c}, {max_c} }}
    }}
    exec {{
        run trans
    }}
    zero {{
        tmp1 = trans->loadRise - trans->capRise
        tmp2 = trans->loadFall - trans->capFall
    }}
}}
        """
        return template.format(**args)

    @staticmethod
    def generate_spice_optim(args):
        template = """
* More info at UltraSim_User.pdf
*----------------------------------------------------------------------
* Optimization setup
*----------------------------------------------------------------------
.measure errorR param='invR - capR' goal=0
.measure errorF param='invF - capF' goal=0
.param Cload=optrange({start_c}, {min_c}, {max_c})
.model optmod opt method=bisection itropt={max_iterations} relin=0.01 relout=0.01
.measure Cl param = 'Cload'
*----------------------------------------------------------------------
* Stimulus
*----------------------------------------------------------------------
.tran 1ps '2*PERIOD' SWEEP OPTIMIZE = optrange
+ RESULTS=errorR,errorF MODEL=optmod
.measure invR
+ TRIG v(c) VAL='{half_vdd}' FALL=1
+ TARG v(d) VAL='{half_vdd}' RISE=1
.measure capR
+ TRIG v(c) VAL='{half_vdd}' FALL=1
+ TARG v(g) VAL='{half_vdd}' RISE=1
.measure invF
+ TRIG v(c) VAL='{half_vdd}' RISE=1
+ TARG v(d) VAL='{half_vdd}' FALL=1
.measure capF
+ TRIG v(c) VAL='{half_vdd}' RISE=1
+ TARG v(g) VAL='{half_vdd}' FALL=1
.end
        """
        return template.format(**args)

    def add_additional_includes(self, stim_file):
        pass

    def run_optimization(self):
        from modules.buffer_stage import BufferStage
        from characterizer.stimuli import stimuli
        import characterizer
        from globals import OPTS
        import debug

        reload(characterizer)

        # in buffer
        in_buffer = BufferStage(
            buffer_stages=self.buffer_stages, height=self.logic_buffers_height)
        in_pex = self.run_pex_extraction(in_buffer, in_buffer.name)
        # driver
        driver = BufferStage(buffer_stages=[self.driver_size], height=self.logic_buffers_height)
        driver_pex = self.run_pex_extraction(driver, driver.name)

        debug.info(2, "DUT name is {}".format(self.dut_name))
        debug.info(2, "Running simulation for corner {}".format(self.corner))

        spice_template = open(self.spice_template, 'r').read()
        vdd_value = self.corner[1]

        args = {
            "vdd_value": vdd_value,
            "PERIOD": self.options.period,
            "in_buffer_name": in_buffer.name,
            "driver_name": driver.name,
            "half_vdd": 0.5 * vdd_value,
            "start_c": self.options.start_c,
            "min_c": self.options.min_c,
            "max_c": self.options.max_c,
            "dut_instance": self.dut_instance,
            "max_iterations": self.options.max_iterations

        }

        if self.instantiate_dummy:
            dummy_str = self.dummy_driver(args)
        else:
            dummy_str = ""

        args["dummy_inst"] = dummy_str

        spice_content = spice_template.format(**args)
        self.stim_file_name = self.prefix("stim.sp")

        with open(self.stim_file_name, "w") as stim_file:
            stim_file.write("simulator lang=spice \n")
            stim = stimuli(stim_file, corner=self.corner)
            stim.write_include(in_pex)
            stim_file.write(".include \"{0}\" \n".format(driver_pex))
            # avoid clash with load pex
            if self.load_pex not in [in_pex, driver_pex]:
                stim_file.write(".include \"{0}\" \n".format(self.load_pex))

            self.add_additional_includes(stim_file)

            stim_file.write(spice_content)

            stim_file.write("\nsimulator lang=spectre\n")
            stim_file.write("simulatorOptions options temp={0} preservenode=all dc_pivot_check=yes"
                            " \n".format(self.corner[2]))

            stim_file.write("saveOptions options save=lvlpub nestlvl=1 pwr=total \n")
            stim_file.write("simulator lang=spice \n")

            if self.options.use_mdl:
                stim_file.write(".PARAM Cload=1f\n")
                OPTS.spectre_command_options = " =mdlcontrol optimize.mdl "

                self.mdl_file = self.prefix("optimize.mdl")
                with open(self.mdl_file, "w") as mdl_file:
                    mdl_file.write(self.generate_mdl(args))
            else:
                stim_file.write(self.generate_spice_optim(args))

        stim.run_sim()

    def get_optimization_result(self):
        with open(self.stim_file_name.replace(".sp", ".log"), "r") as log_file:
            for line in log_file:
                if line.startswith("Optimization completed"):
                    cap_val = float(line.split()[-1])
                    return cap_val
        assert False, "Optimization result not found"

    def run_ac_cap_measurement(self, pin_name, dut):
        from characterizer.stimuli import stimuli
        import characterizer
        reload(characterizer)

        # TODO make configurable
        min_f = 10e6
        max_f = 1e9

        self.stim_file_name = self.prefix("stim.sp")
        with open(self.stim_file_name, "w") as stim_file:
            stim_file.write("simulator lang=spice \n")
            stim = stimuli(stim_file, corner=self.corner)
            stim.write_include(self.load_pex)
            all_pins = dut.pins
            split_index = all_pins.index(pin_name)
            z_pin_index = len(all_pins) - 3
            prefix = " " .join(["gnd"] * split_index)
            suffix = " ".join(["gnd"] * (z_pin_index - split_index))

            dut_statement = "Xdut {} {} {} vdd gnd {}\n".format(prefix, pin_name, suffix,
                                                                dut.name)
            stim_file.write(dut_statement)
            vdd_value = self.corner[1]
            stim_file.write("Vvdd vdd gnd {}\n".format(vdd_value))
            stim_file.write("Vac {} gnd {} AC {}\n".format(pin_name, vdd_value, 1))
            stim_file.write(".save I(Vac)\n".format(pin_name))
            stim_file.write(".ac dec 10 {} {}\n".format(min_f, max_f))
        stim.run_sim()
        from characterizer.simulation.psf_reader import PsfReader
        # TODO output file name by simulator
        sim_data = PsfReader(self.prefix("frequencySweep.ac"))
        f = sim_data.data.get_sweep_values()
        i_data = - np.imag(sim_data.get_signal("Vac:p"))
        # least squares fit
        from scipy.optimize import least_squares

        def least_squares_f_x(x_):
            return np.log(i_data) - np.log(x_[0] + 2 * np.pi * f * x_[1])

        initial_guess = [0, 1e-15]

        best_fit = least_squares(least_squares_f_x, initial_guess)
        _, cap = best_fit.x
        return cap

    def save_result(self, cell_name: str, pin_name: str, value: float,
                    size: float = 1, clear_existing=False,
                    file_suffixes: List[Tuple[str, float]] = None,
                    size_suffixes: List[Tuple[str, float]] = None):
        if self.options.no_save:
            return
        from characterizer.characterization_data import save_data
        save_data(cell_name, pin_name, value, size, clear_existing,
                  file_suffixes, size_suffixes)

    @staticmethod
    def load_data(cell_name, pin_name, sweep_variable="size", file_suffixes=None):
        from characterizer.characterization_data import get_data_file, FLOAT_REGEX
        file_name = get_data_file(cell_name, file_suffixes)
        with open(file_name, "r") as data_file:
            data = json.load(data_file)

        pin_data = data[pin_name]  # type: dict
        search_pattern = "{}_({})".format(sweep_variable, FLOAT_REGEX)
        results = {}
        for key, value in pin_data.items():
            match = re.search(search_pattern, key)
            legend = key.replace(match.group(0), "").strip("_").replace("__", "_")
            if legend not in results:
                results[legend] = []
            results[legend].append([float(match.group(1)), value])
        return results

    @staticmethod
    def plot_results(cell_name, pin_names: Union[List, str], sweep_variable="size",
                     file_suffixes=None, y_labels="Cap (fF)", x_label=None,
                     x_scale=1, y_scale=1e15, show_legend=False,
                     scale_by_x=False, log_x=False, show_plot=True,
                     save_plot=True,
                     save_name_suffix=None, sup_title=None):
        import matplotlib.pyplot as plt
        import numpy as np
        if not x_label:
            x_label = sweep_variable

        if isinstance(pin_names, str):
            pin_names = [pin_names]

        if isinstance(y_labels, str):
            y_labels = [y_labels] * len(pin_names)

        if len(pin_names) == 1:
            subplots = [plt.gca()]
        else:
            _, subplots = plt.subplots(1, ncols=len(pin_names),
                                       sharey=True, figsize=[4 * len(pin_names), 5])

        for j in range(len(pin_names)):
            ax = subplots[j]
            pin_name = pin_names[j]

            results = CharTestBase.load_data(cell_name, pin_name, sweep_variable, file_suffixes)

            keys = list(results.keys())
            for i in range(len(keys)):
                key = keys[i]
                data = np.array(results[key])
                if scale_by_x:
                    y_data = data[:, 0] * data[:, 1]
                else:
                    y_data = data[:, 1]
                plt_func = ax.semilogx if log_x else ax.plot
                plt_func(data[:, 0] * x_scale, y_data * y_scale, "-o", label=key)

            # add legends if not empty
            if "".join(keys) and show_legend:
                ax.legend(keys)
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_labels[j])
            ax.set_title(pin_name)
            ax.grid()
        plt.tight_layout()
        if sup_title is not None:
            plt.subplots_adjust(top=0.9)
            plt.suptitle(sup_title)
        if save_plot:
            from characterizer.characterization_data import get_data_dir
            image_dir = os.path.join(get_data_dir(), "images")
            if not os.path.exists(image_dir):
                os.mkdir(image_dir)
            file_prefix = os.path.join(image_dir, cell_name)
            if save_name_suffix:
                file_prefix += save_name_suffix
            plt.savefig(file_prefix + ".png")
            # plt.savefig(file_prefix + ".pdf")

        if show_plot:
            plt.show()


# http://code.activestate.com/recipes/579018-python-determine-name-and-directory-of-the-top-lev/
for teil in inspect.stack():
    # skip system calls
    if teil[1].startswith("<"):
        continue
    if teil[1].upper().startswith(sys.exec_prefix.upper()):
        continue
    trc = teil[1]

# bypass pydevd during debugging
if trc.endswith("pydevd.py"):
    trc = sys.argv[0]

test_name = os.path.basename(trc)[:-3]
openram_temp = os.path.join(
    os.environ["SCRATCH"], "openram", "characterization", test_name)
CharTestBase.temp_folder = openram_temp
