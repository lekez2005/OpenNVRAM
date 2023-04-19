from base.design import design
from base.library_import import library_import
from globals import OPTS
from modules.bitcell_aligned_array import BitcellAlignedArray
from modules.write_driver import write_driver
from modules.write_driver_array import write_driver_array


class bl_1t1s_write_driver(write_driver):
    pin_names = ("bl bl_sel blb br br_sel brb data data_bar " \
                 "en_bar gnd mask_bar vdd").split() + ["and", "nor"]


@library_import
class write_driver_tap(design):
    """
    Nwell and Psub body taps for write_driver
    """
    lib_name = OPTS.write_driver_tap_mod
    pin_names = ["vdd", "gnd"]


class bl_1t1s_write_driver_array(write_driver_array):
    """
    Array of Masked write drivers
    """

    def add_pins(self):
        BitcellAlignedArray.add_pins(self)

    @property
    def bus_pins(self):
        bus_pins = super().bus_pins
        if OPTS.shared_wwl:
            return bus_pins + ["blb"]
        else:
            return bus_pins + ["blb", "brb"]

    def add_layout_pins(self):
        super().add_layout_pins()

        for pin_name in ["and", "nor"]:
            for bus_index in range(len(self.child_insts)):
                self.copy_layout_pin(self.child_insts[bus_index], pin_name,
                                     f"{pin_name}[{bus_index}]")
