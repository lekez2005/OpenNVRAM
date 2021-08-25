import cam_test_base  # to add appropriate paths
from simulator_base import SimulatorBase


class CamSimulator(SimulatorBase):
    config_template = "config_cam_{}"
    sim_dir_suffix = "cam"
    valid_modes = ["cmos"]

    def get_netlist_gen_class(self):
        from cam_spice_characterizer import CamSpiceCharacterizer
        return CamSpiceCharacterizer
