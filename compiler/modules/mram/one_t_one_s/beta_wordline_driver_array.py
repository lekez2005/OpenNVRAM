"""Support wordline driver array with custom beta for each driver stage"""
import debug
from globals import OPTS
from modules.buffer_stage import BufferStage
from modules.logic_buffer import LogicBuffer
from modules.stacked_wordline_driver_array import stacked_wordline_driver_array
from modules.wordline_driver_array import wordline_driver_array
from pgates.pinv import pinv
from tech import parameter


def extract_beta(**kwargs):
    kwargs = {key: value for key, value in kwargs.items()}
    stages_beta = kwargs.pop("stages_beta")
    stages_beta = [x or 1 for x in stages_beta]
    suffix = "_beta_" + "_".join(['{:.3g}'.format(x) for x in stages_beta])
    suffix = suffix.replace(".", "__")

    return stages_beta, suffix, kwargs


class BetaBufferStages(BufferStage):

    @classmethod
    def get_name(cls, buffer_stages, **kwargs):
        stages_beta, suffix, kwargs = extract_beta(**kwargs)
        return BufferStage.get_name(buffer_stages, **kwargs) + suffix

    def __init__(self, *args, **kwargs):
        self.stages_beta, _, kwargs = extract_beta(**kwargs)
        super().__init__(*args, **kwargs)

    def create_buffer_inv(self, size, index=None):
        beta = self.stages_beta[index] * parameter["beta"]
        return pinv(size=size, height=self.height, contact_nwell=self.contact_nwell,
                    contact_pwell=self.contact_pwell, align_bitcell=self.align_bitcell,
                    fake_contacts=self.fake_contacts, beta=beta)


class BetaLogicBuffer(LogicBuffer):
    @classmethod
    def get_name(cls, buffer_stages, **kwargs):
        stages_beta, suffix, kwargs = extract_beta(**kwargs)
        return LogicBuffer.get_name(buffer_stages, **kwargs) + suffix

    def __init__(self, *args, **kwargs):
        self.stages_beta, _, kwargs = extract_beta(**kwargs)
        super().__init__(*args, **kwargs)

    def create_buffer_mod(self):
        self.buffer_mod = BetaBufferStages(self.buffer_stages, height=self.height,
                                           route_outputs=self.route_outputs,
                                           contact_pwell=self.contact_pwell,
                                           contact_nwell=self.contact_nwell,
                                           align_bitcell=self.align_bitcell,
                                           stages_beta=self.stages_beta)
        self.add_mod(self.buffer_mod)


def create_beta_logic_buffer(self, height):
    if self.stages_beta is None:
        self.stages_beta = OPTS.wordline_stages_beta
    debug.info(2, "stages_beta = ", self.stages_beta)
    self.logic_buffer = BetaLogicBuffer(self.buffer_stages, logic="pnand2",
                                        height=height, route_outputs=False,
                                        route_inputs=False,
                                        contact_pwell=False, contact_nwell=False,
                                        align_bitcell=True,
                                        stages_beta=self.stages_beta)
    self.add_mod(self.logic_buffer)


class BetaWordlineDriverArray(wordline_driver_array):
    def __init__(self, rows, buffer_stages, name=None, stages_beta=None):
        self.stages_beta = stages_beta
        super().__init__(rows, buffer_stages, name)

    def create_modules(self):
        self.bitcell = self.create_mod_from_str(OPTS.bitcell)
        create_beta_logic_buffer(self, self.bitcell.height)


class BetaStackedWordlineDriverArray(stacked_wordline_driver_array):
    def __init__(self, rows, buffer_stages, name=None, stages_beta=None):
        self.stages_beta = stages_beta
        super().__init__(rows, buffer_stages, name)

    def create_modules(self):
        self.bitcell = self.create_mod_from_str(OPTS.bitcell)
        create_beta_logic_buffer(self, 2 * self.bitcell.height)
