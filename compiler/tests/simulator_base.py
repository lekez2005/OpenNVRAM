import argparse
import os
import sys
from importlib import reload
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from testutils import OpenRamTest
else:
    class OpenRamTest:
        pass


class SimulatorBase(OpenRamTest):
    DEFAULT_WORD_SIZE = 32
    sim_dir_suffix = ""
    CMOS_MODE = "cmos"
    valid_modes = [CMOS_MODE]

    def get_sram_class(self):
        from globals import OPTS
        if hasattr(OPTS, "sram_class"):
            return self.load_class_from_opts("sram_class")
        from modules.baseline_sram import BaselineSram
        return BaselineSram

    def create_sram(self):
        from globals import OPTS
        sram_class = self.get_sram_class()
        sram = sram_class(word_size=OPTS.word_size, num_words=OPTS.num_words,
                          num_banks=OPTS.num_banks, words_per_row=OPTS.words_per_row,
                          name="sram1", add_power_grid=True)
        return sram

    def run_simulation(self):
        import debug
        from globals import OPTS

        self.sram = self.create_sram()
        debug.info(1, "Write netlist to file")
        self.sram.sp_write(OPTS.spice_file)

        netlist_generator = self.create_netlist_generator(self.sram)
        netlist_generator.configure_timing(self.sram)
        if self.cmd_line_opts.energy:
            netlist_generator.write_generic_stimulus()
        else:
            netlist_generator.write_delay_stimulus()
        netlist_generator.stim.run_sim()

        debug.info(1, "Read Period = {:3g}".format(netlist_generator.read_period))
        debug.info(1, "Read Duty Cycle = {:3g}".format(netlist_generator.read_duty_cycle))

        debug.info(1, "Write Period = {:3g}".format(netlist_generator.write_period))
        debug.info(1, "Write Duty Cycle = {:3g}".format(netlist_generator.write_duty_cycle))

        debug.info(1, "Trigger delay = {:3g}".format(OPTS.sense_trigger_delay))
        area = self.sram.width * self.sram.height
        debug.info(1, "Area = {:.3g} x {:.3g} = {:3g}".format(self.sram.width, self.sram.height,
                                                              area))

    def get_netlist_gen_class(self):
        from characterizer import SpiceCharacterizer
        return SpiceCharacterizer

    def create_netlist_generator(self, sram):
        import characterizer
        reload(characterizer)
        from globals import OPTS
        delay_class = self.get_netlist_gen_class()
        return delay_class(sram, spfile=OPTS.spice_file,
                           corner=self.corner, initialize=False)

    @classmethod
    def create_arg_parser(cls):
        parser = argparse.ArgumentParser()
        parser.add_argument("-M", "--mode", default=cls.CMOS_MODE,
                            choices=cls.valid_modes,
                            type=str, help="Simulation mode")
        parser.add_argument("--num_words", default=64, type=int)
        parser.add_argument("-C", "--num_cols", default=64, type=int)
        parser.add_argument("-W", "--word_size", default=cls.DEFAULT_WORD_SIZE, type=int)
        parser.add_argument("-B", "--num_banks", default=1, choices=[1, 2], type=int)
        parser.add_argument("-t", "--tech", dest="tech_name", help="Technology name",
                            default="freepdk45")
        parser.add_argument("--simulator", dest="spice_name", help="Simulator name",
                            default="spectre")
        parser.add_argument("--dependent", action="store_true")
        parser.add_argument("--fixed_buffers", action="store_true")
        parser.add_argument("--latched", action="store_true")
        parser.add_argument("--precharge", action="store_true")
        parser.add_argument("--small", action="store_true")
        parser.add_argument("--large", action="store_true")
        parser.add_argument("--schematic", action="store_true")
        parser.add_argument("--run_drc", action="store_true")
        parser.add_argument("--run_lvs", action="store_true")
        parser.add_argument("--run_pex", action="store_true")
        parser.add_argument("--verbose_save", action="store_true")
        parser.add_argument("--skip_write_check", action="store_true")
        parser.add_argument("--skip_read_check", action="store_true")
        parser.add_argument("--energy", default=None, type=int)
        parser.add_argument("-p", "--plot", default=None)
        parser.add_argument("-o", "--analysis_op_index", default=None,
                            type=int, help="which of the ops to analyze")
        parser.add_argument("-b", "--analysis_bit_index", default=None,
                            type=int, help="what bit to analyze and plot")
        return parser

    @classmethod
    def parse_options(cls):

        arg_parser = cls.create_arg_parser()
        options, other_args = arg_parser.parse_known_args()
        cls.cmd_line_opts = options

        sys.argv = [sys.argv[0]] + other_args + ["-t", options.tech_name]

        assert options.num_cols % options.word_size == 0, \
            "Number of columns should be multiple of word size"

        cls.temp_folder = cls.get_sim_directory(cls.cmd_line_opts)

        return options

    def update_global_opts(self):
        options = self.cmd_line_opts
        from globals import OPTS
        OPTS.use_pex = not options.schematic
        OPTS.run_drc = options.run_drc
        OPTS.run_lvs = options.run_lvs
        OPTS.run_pex = options.run_pex
        OPTS.spice_name = options.spice_name
        OPTS.verbose_save = options.verbose_save

        OPTS.num_banks = options.num_banks
        OPTS.word_size = self.word_size = options.word_size
        OPTS.words_per_row = self.words_per_row = int(options.num_cols / options.word_size)
        OPTS.num_words = options.num_words

        OPTS.run_optimizations = not options.fixed_buffers
        OPTS.energy = options.energy

        OPTS.independent_banks = not options.dependent

        if options.energy:
            OPTS.pex_spice = OPTS.pex_spice.replace("_energy", "")

    @classmethod
    def get_sim_directory(cls, cmd_line_opts):
        bank_suffix = "_bank2" if cmd_line_opts.num_banks == 2 else ""
        if cmd_line_opts.num_banks == 2 and cmd_line_opts.dependent:
            bank_suffix += "_depend"

        if not cmd_line_opts.word_size == cls.DEFAULT_WORD_SIZE:
            word_size_suffix = "_w{}".format(cmd_line_opts.word_size)
        else:
            word_size_suffix = ""
        schem_suffix = "_schem" if cmd_line_opts.schematic else ""
        if cmd_line_opts.precharge:
            schem_suffix = "_precharge" + schem_suffix

        energy_suffix = "_energy" if cmd_line_opts.energy else ""

        op = cmd_line_opts
        sim_directory = f"{op.mode}_{op.num_words}_c_{op.num_cols}" \
                        f"{word_size_suffix}{bank_suffix}{schem_suffix}{energy_suffix}"
        openram_temp_ = os.path.join(os.environ["SCRATCH"], "openram", cls.sim_dir_suffix,
                                     cmd_line_opts.tech_name, sim_directory)
        return openram_temp_