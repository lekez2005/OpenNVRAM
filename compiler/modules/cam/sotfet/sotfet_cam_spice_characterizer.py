import numpy as np

from globals import OPTS
from modules.cam.cam_spice_characterizer import CamSpiceCharacterizer
from modules.cam.sotfet.sotfet_cam_dut import SotfetCamDut
from modules.cam.sotfet.sotfet_cam_probe import SotfetCamProbe
from modules.mram.mram_sim_steps_generator import MramSimStepsGenerator


class SotfetCamSpiceCharacterizer(CamSpiceCharacterizer, MramSimStepsGenerator):

    def __init__(self, *args, **kwargs):
        CamSpiceCharacterizer.__init__(self, *args, **kwargs)
        self.one_t_one_s = getattr(OPTS, "one_t_one_s", False)
        self.two_step_pulses["write_trig"] = 1

    def create_probe(self):
        self.probe = SotfetCamProbe(self.sram, OPTS.pex_spice)

    def create_dut(self):
        stim = SotfetCamDut(self.sf, self.corner)
        stim.words_per_row = self.sram.words_per_row
        return stim

    def write_ic(self, ic, col_node, col_voltage):
        phi = 0.1 * OPTS.llg_prescale
        theta = np.arccos(col_voltage) * OPTS.llg_prescale
        theta_2 = np.arccos(-col_voltage) * OPTS.llg_prescale

        phi_node = col_node.replace(".state", ".phi")
        theta_node = col_node.replace(".state", ".theta")

        phi_2_node = col_node.replace("XI0.state", "XI1.phi")
        theta_2_node = col_node.replace("XI0.state", "XI1.theta")

        ic.write(".ic V({})={} \n".format(phi_node, phi))
        ic.write(".ic V({})={} \n".format(theta_node, theta))
        ic.write(".ic V({})={} \n".format(phi_2_node, phi))
        ic.write(".ic V({})={} \n".format(theta_2_node, theta_2))

        # state_node_2 = col_node.replace("XI0.state", "XI1.mz")
        # for node in [phi_node, theta_node, phi_2_node, theta_2_node, state_node_2]:
        #     ic.write(f".probe tran v({node})\n")
