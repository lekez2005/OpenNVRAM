from modules.baseline_bank import BaselineBank
from modules.baseline_latched_control_buffers import LatchedControlBuffers


class CmosBank(BaselineBank):

    def create_control_buffers(self):
        self.control_buffers = LatchedControlBuffers(self)
        self.add_mod(self.control_buffers)
