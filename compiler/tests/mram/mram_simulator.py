#!/usr/bin/env python3

"""
Run a delay test on mram using spectre/hspice
"""
import test_base
from simulator_base import SimulatorBase


class MramSimulator(SimulatorBase):
    sim_dir_suffix = "mram"
    SOTFET_MODE = "sotfet"
    SOT_MODE = "sot"
    valid_modes = [SOTFET_MODE, SOT_MODE]

    @classmethod
    def create_arg_parser(cls):

        parser = super(MramSimulator, cls).create_arg_parser()
        parser.add_argument("--precharge", action="store_true")
        return parser

    @classmethod
    def parse_options(cls):
        options = super(MramSimulator, cls).parse_options()

        cls.config_template = f"config_mram_{options.mode}_{{}}"
        return options

    def get_netlist_gen_class(self):
        from mram.mram_sim_steps_generator import MramSimStepsGenerator
        return MramSimStepsGenerator

    @classmethod
    def get_sim_directory(cls, cmd_line_opts):

        cls.sim_dir_suffix = f"{cmd_line_opts.mode}_mram"
        openram_temp_ = SimulatorBase.get_sim_directory(cmd_line_opts)
        suffix = ""
        if cmd_line_opts.precharge:
            suffix = "_precharge"
        return openram_temp_ + suffix
