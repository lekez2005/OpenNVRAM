import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cam_test_base import CamTestBase
from cam_simulator import CamSimulator


class SotfetCamSimulatorBase(CamSimulator, CamTestBase):
    config_template = "config_cam_sotfet_{}"
    valid_modes = ["sotfet"]

    @classmethod
    def create_arg_parser(cls):
        parser = super(SotfetCamSimulatorBase, cls).create_arg_parser()
        parser.add_argument("--pcam", action="store_true", help="Whether pcam/scam")
        return parser

    def setUp(self):
        super().setUp()
        self.update_global_opts()

    @classmethod
    def get_sim_directory(cls, cmd_line_opts):
        suffix = "pcam" if cmd_line_opts.pcam else "scam"
        cls.sim_dir_suffix = f"cam/{suffix}"
        return super(SotfetCamSimulatorBase, cls).get_sim_directory(cmd_line_opts)

    def update_global_opts(self):
        super().update_global_opts()
        from globals import OPTS
        if self.cmd_line_opts.pcam:
            OPTS.sotfet_cam_mode = "pcam"
            OPTS.bitcell_mod = "cam/sotfet_cam_cell"
            OPTS.sotfet_mode = "and"
            OPTS.schematic_model_file = "cam/sotfet_pcam_schematic.sp"
            OPTS.mram_bitcell = "cam/sotfet_cam_cell"
        else:
            OPTS.sotfet_cam_mode = "scam"
            OPTS.bitcell_mod = "cam/sotfet_scam_cell"
            OPTS.sotfet_mode = "or"
            OPTS.schematic_model_file = "cam/sotfet_scam_schematic.sp"
            OPTS.mram_bitcell = "cam/sotfet_scam_cell"
        SotfetCamSimulatorBase.sim_dir_suffix = f"cam/{OPTS.sotfet_mode}"

    def get_netlist_gen_class(self):
        from modules.cam.sotfet.sotfet_cam_spice_characterizer \
            import SotfetCamSpiceCharacterizer
        return SotfetCamSpiceCharacterizer
