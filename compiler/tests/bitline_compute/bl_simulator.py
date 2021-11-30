from simulator_base import SimulatorBase


class BlSimulator(SimulatorBase):
    sim_dir_suffix = "bitline_compute"

    SERIAL_MODE = "serial"
    PAR_MODE = "parallel"
    BASELINE_MODE = "baseline"
    valid_modes = [PAR_MODE, SERIAL_MODE, BASELINE_MODE]

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
        return parser

    @classmethod
    def validate_options(cls, options):
        cls.serial = options.mode == cls.SERIAL_MODE
        cls.baseline = options.mode == cls.BASELINE_MODE
        cls.latched = not options.mirrored

        if cls.serial:
            options.alu_word_size = 1
        if not options.word_size:
            options.word_size = options.num_cols

    def update_global_opts(self):
        from globals import OPTS
        OPTS.alu_word_size = self.cmd_line_opts.alu_word_size

        super().update_global_opts()

    def get_netlist_gen_class(self):
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
