from globals import OPTS
from modules import write_driver_array


class cam_write_driver_array(write_driver_array.write_driver_array):
    """
    Array of CAM write drivers
    """

    def get_name(self):
        return "cam_write_driver_array"

    @property
    def mod_name(self):
        return OPTS.write_driver

    @property
    def tap_name(self):
        return None

