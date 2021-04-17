from base.design import design
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.write_driver_array import write_driver_array


@library_import
class sot_write_driver_ref(design):
    pin_names = "bl br en en_bar gnd vdd".split()
    lib_name = OPTS.write_driver_ref_mod


class SotWriteDriverArray(write_driver_array):

    def create_array(self):
        super().create_array()
        self.ref_write_driver = sot_write_driver_ref()
        self.add_mod(self.ref_write_driver)

        x_offset = OPTS.reference_cell_x
        self.ref_driver_inst = self.add_inst("ref_driver", self.ref_write_driver,
                                             vector(x_offset, 0))
        self.connect_inst("ref_bl ref_br en en_bar gnd vdd".split())

    def add_layout_pins(self):
        super().add_layout_pins()
        pin_names = ["ref_bl", "ref_br"]
        self.add_pin_list(pin_names)
        for pin_name in pin_names:
            self.copy_layout_pin(self.ref_driver_inst, pin_name.replace("ref_", ""), pin_name)
