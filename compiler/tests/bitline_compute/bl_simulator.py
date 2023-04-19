import os

from simulator_base import SimulatorBase


class BlSimulator(SimulatorBase):
    sim_dir_suffix = "bitline_compute"

    SERIAL_MODE = "serial"
    PAR_MODE = "parallel"
    BASELINE_MODE = "baseline"
    ONE_T_ONE_S = "1t1s"
    valid_modes = [PAR_MODE, SERIAL_MODE, BASELINE_MODE, ONE_T_ONE_S]

    def create_sram(self):
        sram = super().create_sram()
        if not self.baseline:
            # there is mask_in for the purposes of delay characterization
            sram.bank.has_mask_in = True
            sram.has_mask_in = True
        return sram

    @classmethod
    def create_arg_parser(cls):
        parser = super(BlSimulator, cls).create_arg_parser()
        cls.change_parser_arg_attribute(parser, "num_words", "default", 64)
        cls.change_parser_arg_attribute(parser, "num_cols", "default", 64)
        cls.change_parser_arg_attribute(parser, "word_size", "default", None)
        parser.add_argument("--alu_word_size", "--alu", default=cls.DEFAULT_WORD_SIZE, type=int)
        parser.add_argument("--mirrored", action="store_true")
        parser.add_argument("--sim_rw_only", action="store_true")
        parser.add_argument("--shared_wwl", action="store_true")
        return parser

    @classmethod
    def validate_options(cls, options):
        cls.serial = options.mode == cls.SERIAL_MODE
        cls.baseline = options.mode == cls.BASELINE_MODE
        cls.latched = not options.mirrored

        cls.one_t_one_s = options.mode == cls.ONE_T_ONE_S
        if cls.one_t_one_s:
            cls.config_template = "config_bl_1t1s_{}"
            if options.shared_wwl:
                os.environ["SHARE_WWL"] = "1"

        if cls.serial:
            options.alu_word_size = 1
        if not options.word_size:
            options.word_size = options.num_cols

    def update_global_opts(self):
        from globals import OPTS
        OPTS.alu_word_size = self.cmd_line_opts.alu_word_size
        OPTS.sim_rw_only = self.cmd_line_opts.sim_rw_only

        super().update_global_opts()

    def get_netlist_gen_class(self):
        if self.one_t_one_s:
            from modules.bitline_compute.one_t_one_s.bl_1t1s_spice_characterizer \
                import Bl1t1sSpiceCharacterizer
            return Bl1t1sSpiceCharacterizer
        from modules.bitline_compute.bitline_spice_characterizer import BitlineSpiceCharacterizer
        return BitlineSpiceCharacterizer

    @classmethod
    def get_sim_directory(cls, cmd_line_opts):
        openram_temp_ = super(BlSimulator, cls).get_sim_directory(cmd_line_opts)
        if not cls.serial and not cls.baseline:
            openram_temp_ += f"_alu{cmd_line_opts.alu_word_size}"
        if cmd_line_opts.mirrored:
            openram_temp_ += "_mirrored"
        return openram_temp_
