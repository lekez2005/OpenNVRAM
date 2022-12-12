import argparse
import csv
import itertools
import math
import os
import pathlib
import subprocess
import sys
from abc import ABC
from datetime import datetime
from tempfile import NamedTemporaryFile
from types import SimpleNamespace

import debug

OP_FIRST_READ = "fr"
OP_FIRST_WRITE = "fw"
OP_SECOND_WRITE = "sw"
OP_SECOND_READ = "sr"
OP_SENSE_TIME = "st"
OP_ALL = "all"

OPENRAM_HOME = os.getenv("OPENRAM_HOME")
OPENRAM_TECH = os.getenv("OPENRAM_TECH")


def format_float(value, width=7, decimals=4):
    format_str = f"{{0:<{width}.{decimals}g}} ps "
    return format_str.format(value * 1e3)


class ProcessRunner:
    @staticmethod
    def run_script(script, script_args, cmd_line_options, cwd=None, verbose=0,
                   real_time_output=True, capture_output=True, **kwargs):
        if cwd is None:
            cwd = os.getcwd()
        command, _kwargs = ProcessRunner.create_process(script, script_args, cwd,
                                                        cmd_line_options)
        if verbose > 0:
            command.append("-" + "v" * verbose)
        else:
            command.append("-v")
            real_time_output = False
        kwargs.update(_kwargs)
        return ProcessRunner.run_process(command, verbose, real_time_output,
                                         capture_output=capture_output, **kwargs)

    @staticmethod
    def create_process(script, script_args, cwd, cmd_line_options):
        from base.run_command import create_pre_exec_fcn
        command = ["python", script] + script_args

        for key in ["mode", "num_cols", "num_words", "word_size", "tech"]:
            if hasattr(cmd_line_options, key):
                command.append(f"--{key}={getattr(cmd_line_options, key)}")

        kwargs = dict(cwd=cwd, preexec_fn=create_pre_exec_fcn())
        return command, kwargs

    @staticmethod
    def run_process(command, verbose=0, real_time_output=True,
                    capture_output=True, **kwargs):
        if verbose > 0:
            print(" ".join(command))

        if real_time_output:
            if not capture_output:
                return subprocess.run(command, **kwargs)
            output = ""
            process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, **kwargs)
            while process.stdout:
                line = process.stdout.readline().decode()
                if not line:
                    break
                print(line, end="")
                output += line
            process.wait()
            process.stdout = output
            return process
        elif capture_output:
            return subprocess.run(command, capture_output=True, **kwargs)
        else:
            return subprocess.run(command, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, **kwargs)


class BinaryDelayOptimizer(ABC):
    def get_simulation_script(self):
        raise NotImplementedError

    def get_read_evaluator_script(self):
        raise NotImplementedError

    def get_write_evaluator_script(self):
        raise NotImplementedError

    def get_first_write_script(self):
        raise NotImplementedError

    def get_first_read_script(self):
        raise NotImplementedError

    def get_config_file_name(self) -> str:
        raise NotImplementedError

    def set_safe_second_write(self):
        self.second_write = 2 * self.second_write

    def set_safe_second_read(self):
        sense_time = self.second_read - self.sense_trigger_delay
        self.sense_trigger_delay = (self.cmd_line_options.safe_read_scale_factor *
                                    self.sense_trigger_delay)
        self.second_read = (self.sense_trigger_delay + sense_time +
                            self.cmd_line_options.sense_margin)

    def restore_second_write(self, original_value):
        self.second_write = original_value

    def restore_second_read(self, original_value):
        sense_time = self.default_sense_time
        self.second_read = original_value
        self.sense_trigger_delay = original_value - sense_time

    @staticmethod
    def get_timing_params():
        return ["first_read", "first_write", "second_read", "second_write",
                "sense_trigger_delay"]

    def load_config_file_path(self):
        config_name = self.get_config_file_name()
        if os.path.isabs(config_name):
            return config_name
        for env_val in [OPENRAM_HOME, OPENRAM_TECH]:
            config_file = subprocess.check_output(["find", env_val, "-name",
                                                   config_name]).decode()
            if config_file:
                config_file = config_file.strip()
                break
        assert config_file, f"Invalid config {config_name}"
        return config_file

    def get_sim_dir(self):
        """Get sim directory by running importing simulation script and getting temp_folder
        Assumes test class name in simulation script ends with 'Test'
        """
        with NamedTemporaryFile() as tmp:
            sim_script, work_dir, args = self.get_simulation_script()
            sim_module = sim_script[:-3]
            tmp.write(f"""
import inspect, sys
sys.path.insert(0, "{work_dir}")
sim_script = __import__("{sim_module}")
members = inspect.getmembers(sim_script)
for member in inspect.getmembers(sim_script):
    if member[0].endswith('Test') and "{sim_module}" in str(member[1]):
        cls = member[1]
        cls.parse_options()
        print(f"temp_dir={{cls.temp_folder}}")
""".encode())
            tmp.flush()

            def process_func():
                return tmp.name, work_dir, args

            process = self.run_process(process_func, capture_output=True,
                                       real_time_output=False)[0]
            if process.returncode == 0:
                output = process.stdout.decode()
                return output.split("temp_dir=")[1].strip()
        return None

    def initialize_openram(self):
        config_file = self.load_config_file_path()
        sys.path.append(OPENRAM_HOME)
        sys.path.append(os.path.join(OPENRAM_HOME, "tests"))

        argv = [x for x in sys.argv]
        sys.argv = [argv[0], "-t", self.cmd_line_options.tech]
        import globals, debug
        globals.parse_args()
        globals.init_openram(config_file)
        sys.argv = argv
        self.debug = debug
        self.config_file = config_file

    @staticmethod
    def create_parser():
        parser = argparse.ArgumentParser()
        parser.add_argument("-t", "--tech", default="freepdk45")
        parser.add_argument("-c", "--num_cols", type=int, default=256)
        parser.add_argument("-r", "--num_words", type=int, default=128)
        parser.add_argument("-w", "--word_size", default=32, type=int)
        parser.add_argument("-o", "--operation", default=OP_ALL,
                            choices=[OP_FIRST_READ, OP_FIRST_WRITE,
                                     OP_SECOND_WRITE, OP_SECOND_READ, OP_SENSE_TIME,
                                     OP_ALL])
        default_tolerance = float(os.getenv("OPENRAM_TIMING_TOLERANCE", "0.01"))
        parser.add_argument("--max_tries", default=15, type=int)
        parser.add_argument("--tolerance", default=default_tolerance, type=float)
        parser.add_argument("--increment_factor", default=1.2, type=float,
                            help="How much to increase or decrease after success or"
                                 " failure if opposite bound is yet to be defined")
        parser.add_argument("--first_write_margin", default=0.02, type=float)
        parser.add_argument("--first_read_margin", default=0.02, type=float)
        parser.add_argument("--second_write_margin", default=0.0, type=float)
        parser.add_argument("--second_read_margin", default=0.0, type=float)
        parser.add_argument("--safe_read_scale_factor", default=2, type=float)
        parser.add_argument("--sense_margin", default=0.1, type=float)
        parser.add_argument("-v", "--verbose", action="count", default=0,
                            help="Increase the verbosity level")
        parser.add_argument("--continue", action="store_true", dest="continue_")
        return parser

    def initialize_timing(self):
        from globals import OPTS
        options = self.cmd_line_options

        words_per_row = int(options.num_cols / options.word_size)
        num_rows = int(options.num_words / words_per_row)
        OPTS.use_pex = "--schematic" not in self.other_args

        bank = SimpleNamespace(num_rows=num_rows, num_cols=options.num_cols,
                               words_per_row=int(options.num_cols / options.word_size))
        sram = SimpleNamespace(bank=bank)
        _ = OPTS.configure_timing(sram, OPTS)
        self.first_read, self.first_write, self.second_read, self.second_write = _

        for param_name in self.get_timing_params():
            param_value = getattr(self, param_name, None)
            if param_value is None:
                param_value = getattr(OPTS, param_name)
            setattr(self, param_name, param_value)
            setattr(self, f"default_{param_name}", param_value)

        self.default_sense_time = self.default_second_read - self.default_sense_trigger_delay

    def reset_timing_from_defaults(self):
        for param_name in self.get_timing_params():
            setattr(self, param_name, getattr(self, f"default_{param_name}"))

    def format_timing_log(self, value, index):
        max_width = len(self.timing_headers[index])
        if index == 0:
            max_width = len("second_write")
        if isinstance(value, float):
            suffix = ".4f"
        else:
            value = str(value)
            suffix = ""
        format = f"{{value:>{max_width}{suffix}}}"
        return format.format(value=value)

    def get_log_file_name(self):
        options = self.cmd_line_options
        size_suffix = f"_c{options.num_cols}-w{options.num_words}"
        time_suffix = datetime.now().strftime("_%y:%m:%d_%H:%M:%-S")
        time_suffix = ""
        return f"optim-log{size_suffix}{time_suffix}.txt"

    def initialize_logger(self):
        from globals import OPTS
        options = self.cmd_line_options
        sim_dir = self.sim_dir or OPTS.openram_temp
        if not os.path.exists(sim_dir):
            pathlib.Path(sim_dir).mkdir(parents=True, exist_ok=True)

        file_name = os.path.join(sim_dir, self.get_log_file_name())

        self.timing_headers = ["op_name", "success"] + self.get_timing_params()

        if options.continue_ and os.path.exists(file_name):
            with open(file_name, "r") as f:
                f.readline()  # skip header
                existing_data = csv.reader(f, delimiter=',')
                existing_data = list(sorted(existing_data, key=lambda x: x[0]))
                self.existing_data = {key.strip(): list(value) for key, value in
                                      itertools.groupby(existing_data, key=lambda x: x[0])}
        else:
            self.existing_data = {}
            with open(file_name, "w") as f:
                f.write(", ".join([self.format_timing_log(self.timing_headers[i], i)
                                   for i in range(len(self.timing_headers))]))
                f.write("\n")
        return file_name

    def log_timing(self, operation_name, success):
        with open(self.log_file_name, "a") as f:
            timings = [operation_name, success]
            for param_name in self.get_timing_params():
                timings.append(getattr(self, param_name))
            line = ", ".join([self.format_timing_log(timings[i], i)
                              for i in range(len(timings))])
            line += "\n"
            f.write(line)

    def print_log(self):
        with open(self.log_file_name, "r") as f:
            print(f.read())

    def ceil_tolerance(self, value, tolerance=None, scale=1e9):
        if tolerance is None:
            tolerance = self.cmd_line_options.tolerance
        if isinstance(value, str):
            value = float(value)
        value *= scale
        return math.ceil(value * 1 / tolerance) / (1 / tolerance)

    def update_environment_variable(self):
        env_values = []
        for param_name in self.get_timing_params():
            value = getattr(self, param_name)
            env_values.append(f"{param_name}={value}")

        os.environ["OPENRAM_OVERRIDE_TIMING"] = ",".join(env_values)

    def __init__(self):
        self.cmd_line_options, self.other_args = self.create_parser().parse_known_args()
        self.verbose = self.cmd_line_options.verbose > 0
        self.initialize_openram()
        self.sim_dir = self.get_sim_dir()
        self.initialize_timing()
        self.log_file_name = self.initialize_logger()
        self.is_first_sim = True

    def run_optimization(self, start_value, operation_name, pre_sim_update,
                         post_sim_update, evaluation_func,
                         tolerance=None, lower_bound=None):
        lower_bound, upper_bound = self.get_bounds_from_existing_data(lower_bound, operation_name)

        if tolerance is None:
            tolerance = self.cmd_line_options.tolerance
        if lower_bound is None:
            lower_bound = self.cmd_line_options.tolerance

        if upper_bound is not None:
            if upper_bound - lower_bound < tolerance:
                post_sim_update(upper_bound)
                print(f"Optimized: {format_float(upper_bound)}")
                return
            else:
                start_value = 0.5 * (upper_bound + lower_bound)
        debug.info(1, "Start value = %.3g, LB = %.3g, UB = %.3g",
                   start_value, lower_bound, upper_bound)

        from characterizer.binary_search import BinarySearch

        def objective_func(current_value):
            pre_sim_update(current_value)
            success, val_str = self.run_and_check_sim(evaluation_func,
                                                      current_value)
            self.log_timing(operation_name, success)
            if success:
                post_sim_update(current_value)
            return success, val_str

        searcher = BinarySearch(objective_func=objective_func, tolerance=tolerance,
                                start_value=start_value, lower_bound=lower_bound,
                                upper_bound=upper_bound,
                                increment_factor=self.cmd_line_options.increment_factor,
                                max_tries=self.cmd_line_options.max_tries)
        return searcher.optimize()

    def run(self):
        operation = self.cmd_line_options.operation
        try:
            if operation == OP_FIRST_READ:
                self.optimize_first_read()
            elif operation == OP_FIRST_WRITE:
                self.optimize_first_write()
            elif operation == OP_SECOND_WRITE:
                self.optimize_second_write()
            elif operation == OP_SECOND_READ:
                self.optimize_second_read()
            elif operation == OP_SENSE_TIME:
                self.optimize_sense_time()
            elif operation == OP_ALL:
                self.optimize_all()
            else:
                raise NotImplementedError
            self.print_log()
        except KeyboardInterrupt:
            self.print_log()

    def optimize_all(self):

        def ceil(value):
            return self.ceil_tolerance(value, scale=1)

        options = self.cmd_line_options

        print("First Write:")
        self.optimize_first_write()
        self.default_first_write = ceil(self.default_first_write + options.first_write_margin)
        print("Second Write:")
        self.optimize_second_write()
        self.default_second_write = ceil(self.default_second_write + options.second_write_margin)
        print("First Read:")
        self.optimize_first_read()
        self.default_first_read = ceil(self.default_first_read + options.first_read_margin)
        print("Second Read:")
        self.optimize_second_read()
        sense_time = self.default_first_read - self.default_sense_trigger_delay
        self.default_sense_trigger_delay = ceil(self.default_sense_trigger_delay)
        self.default_second_read = self.default_sense_trigger_delay + sense_time
        print("Sense Time:")
        self.optimize_sense_time()
        print("final:")
        self.default_second_write -= options.second_write_margin
        self.reset_timing_from_defaults()
        self.log_timing("final", True)

    @staticmethod
    def is_failed_output(output):
        return "failure:" in output

    def run_and_check_sim(self, verification_script_func, current_value):
        sim_process = self.run_simulation()

        if sim_process and sim_process.returncode > 0:
            processes = [sim_process]
        else:
            processes = self.run_process(verification_script_func, capture_output=True,
                                         real_time_output=self.verbose)
        for process in processes:
            if process.returncode == 0:
                output = process.stdout if self.verbose else process.stdout.decode()
                if self.is_failed_output(output):
                    return False, format_float(current_value)
            else:
                return False, format_float(current_value)
        return True, format_float(current_value)

    def get_value_from_existing_data(self, operation_name, attempt_data):
        param_names = self.get_timing_params()
        if operation_name in param_names:
            value = float(attempt_data[2 + param_names.index(operation_name)])
        elif operation_name == "sense_time":
            value = (float(attempt_data[2 + param_names.index("second_read")]) -
                     float(attempt_data[2 + param_names.index("sense_trigger_delay")]))
        else:
            raise ValueError(f"Invalid Operation name {operation_name}")
        return value

    def get_bounds_from_existing_data(self, lower_bound, operation_name):

        upper_bound = None

        if operation_name not in self.existing_data:
            return lower_bound, upper_bound
        param_names = self.get_timing_params()
        existing_data = self.existing_data[operation_name]
        for attempt_data in existing_data:
            value = self.get_value_from_existing_data(operation_name, attempt_data)
            success = attempt_data[1].strip() == 'True'
            if success:
                if operation_name == "second_read":
                    # TODO make this more systematic
                    sense_trigger_delay = float(attempt_data[2 + param_names.index(
                        "sense_trigger_delay")])
                    self.default_sense_trigger_delay = min(self.default_sense_trigger_delay,
                                                           sense_trigger_delay)
                if upper_bound is None:
                    upper_bound = value
                else:
                    upper_bound = min(value, upper_bound)
            else:
                if lower_bound is None:
                    lower_bound = value
                else:
                    lower_bound = max(lower_bound, value)
        return lower_bound, upper_bound

    def optimize_first_read(self):

        def pre_sim_update(value):
            self.first_read = value
            self.first_write = value

        def post_sim_update(value):
            self.default_first_read = min(self.default_first_read, value)

        start_value = self.default_first_read
        self.default_first_read = math.inf

        original_second_read = self.second_read
        self.set_safe_second_read()

        success = self.run_optimization(start_value, "first_read",
                                        pre_sim_update, post_sim_update,
                                        self.get_first_read_script)
        self.restore_second_read(original_second_read)
        return success

    def optimize_first_write(self):

        def pre_sim_update(value):
            self.first_read = value
            self.first_write = value

        def post_sim_update(value):
            self.default_first_write = min(self.default_first_write, value)

        start_value = self.default_first_write
        self.default_first_write = math.inf

        original_second_write = self.second_write
        self.set_safe_second_write()

        success = self.run_optimization(start_value, "first_write",
                                        pre_sim_update, post_sim_update,
                                        self.get_first_write_script)
        self.restore_second_write(original_second_write)
        return success

    def get_second_write_update_callbacks(self):

        def pre_sim_update(value):
            self.second_write = value

        def post_sim_update(value):
            self.default_second_write = min(self.second_write, value)

        return pre_sim_update, post_sim_update, None

    def optimize_second_write(self):

        pre_sim_update, post_sim_update, lower_bound = self.get_second_write_update_callbacks()

        self.reset_timing_from_defaults()
        start_value = self.default_second_write
        self.default_second_write = math.inf
        success = self.run_optimization(start_value, "second_write",
                                        pre_sim_update, post_sim_update,
                                        self.get_write_evaluator_script,
                                        lower_bound=lower_bound)
        return success

    def optimize_second_read(self):
        sense_time = self.default_second_read - self.default_sense_trigger_delay
        sense_margin = self.cmd_line_options.sense_margin

        def pre_sim_update(value):
            self.second_read = value + sense_margin
            self.sense_trigger_delay = self.second_read - sense_time - sense_margin

        def post_sim_update(value):
            self.default_second_read = min(self.default_second_read, value)
            self.default_sense_trigger_delay = min(self.default_sense_trigger_delay,
                                                   self.sense_trigger_delay)

        self.reset_timing_from_defaults()
        start_value = getattr(self, "default_second_read")
        self.default_second_read = math.inf
        self.default_sense_trigger_delay = math.inf
        success = self.run_optimization(start_value, "second_read",
                                        pre_sim_update, post_sim_update,
                                        self.get_read_evaluator_script)
        return success

    def optimize_sense_time(self):

        def pre_sim_update(value):
            self.second_read = sense_trigger_delay + value

        def post_sim_update(value):
            self.default_second_read = min(self.default_second_read,
                                           sense_trigger_delay + value)

        sense_trigger_delay = (self.default_sense_trigger_delay +
                               self.cmd_line_options.second_read_margin)
        start_value = self.default_sense_time

        self.reset_timing_from_defaults()

        self.default_second_read = math.inf
        success = self.run_optimization(start_value, "sense_time",
                                        pre_sim_update, post_sim_update,
                                        self.get_read_evaluator_script)
        return success

    def run_simulation(self):
        self.update_environment_variable()

        if not self.is_first_sim:
            for key in ["--run_drc", "--run_lvs", "--run_pex"]:
                if key in self.other_args:
                    self.other_args.remove(key)

        self.is_first_sim = False
        real_time = self.verbose
        return self.run_process(self.get_simulation_script, capture_output=False,
                                real_time_output=real_time)[0]

    def run_process(self, process_func, capture_output=True, real_time_output=None, **kwargs):
        if real_time_output is None:
            real_time_output = self.cmd_line_options.verbose > 0
        scripts = process_func()
        if not isinstance(scripts, list):
            scripts = [scripts]

        processes = []
        for script_name, work_dir, args in scripts:
            if args is None:
                args = self.other_args
            process = ProcessRunner.run_script(script_name, args,
                                               cmd_line_options=self.cmd_line_options,
                                               verbose=self.cmd_line_options.verbose,
                                               real_time_output=real_time_output,
                                               cwd=work_dir, capture_output=capture_output,
                                               **kwargs)
            processes.append(process)
        return processes
