#!/usr/bin/env python3

"""
Run a delay test on mram using spectre/hspice
"""
from simulator_base import SimulatorBase


class MramSimulator(SimulatorBase):
    sim_dir_suffix = "mram"
    SOTFET_MODE = "sotfet"
    SOT_MODE = "sot"
    ONE_T_ONE_S = "1t1s"
    valid_modes = [SOTFET_MODE, SOT_MODE, ONE_T_ONE_S]

    @classmethod
    def create_arg_parser(cls):

        parser = super(MramSimulator, cls).create_arg_parser()
        parser.add_argument("--precharge", action="store_true")
        return parser

    def update_global_opts(self):
        super().update_global_opts()
        from globals import OPTS
        OPTS.precharge_bl = self.cmd_line_opts.precharge

    @classmethod
    def parse_options(cls):
        options = super(MramSimulator, cls).parse_options()

        cls.config_template = f"config_mram_{options.mode}_{{}}"
        return options

    def get_netlist_gen_class(self):
        from modules.mram.mram_sim_steps_generator import MramSimStepsGenerator
        return MramSimStepsGenerator

    @classmethod
    def get_sim_directory(cls, cmd_line_opts):
        cls.sim_dir_suffix = f"{cmd_line_opts.mode}_mram"
        openram_temp_ = super(MramSimulator, cls).get_sim_directory(cmd_line_opts)
        suffix = ""
        if cmd_line_opts.precharge:
            suffix = "_precharge"
        return openram_temp_ + suffix
