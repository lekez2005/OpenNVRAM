from characterizer import stimuli
from globals import OPTS
from modules.cam.cam import Cam


class CamDut(stimuli):
    def instantiate_sram(self, sram: Cam):
        super().instantiate_sram(sram)
        self.gen_constant("search_ref", OPTS.sense_amp_vref, gnd_node="gnd")
