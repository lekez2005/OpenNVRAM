import custom_transistors

from base.design import design
from pgates.pinv import pinv
from pgates.ptx import ptx
from pgates.ptx_spice import ptx_spice


class HighVoltage:
    voltage_mode = custom_transistors.HIGH_VOLTAGE

    def setup_drc_constants(self: design):
        custom_transistors.set_high_voltage()
        super().setup_drc_constants()

    @classmethod
    def get_name(cls, *args, **kwargs):
        name = super().get_name(*args, **kwargs)
        return name + "_hv"


class ptx_5v(HighVoltage, ptx):
    pass


class ptx_spice_5v(HighVoltage, ptx_spice):
    pass


class pinv_5v(HighVoltage, pinv):
    pass
