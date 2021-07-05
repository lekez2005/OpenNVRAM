from base.design import design
from base.geometry import MIRROR_Y_AXIS, NO_MIRROR
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.shared_decoder.tgate_column_mux_array import tgate_column_mux_array


@library_import
class reference_column_mux(design):
    pin_names = "bl<1> bl<0> bl_out br<1> br<0> br_out gnd vdd".split()
    lib_name = OPTS.reference_column_mux_mod


class SotColumnMuxArray(tgate_column_mux_array):
    def create_modules(self):
        super().create_modules()
        self.ref_mux = reference_column_mux()
        self.add_mod(self.ref_mux)

    @staticmethod
    def get_ref_nets():
        return ("ref_bl[{0}] ref_bl[{1}] ref_br[{0}] ref_br[{1}] "
                "ref_bl_out ref_br_out").format(0, 1)

    def add_pins(self):
        super().add_pins()
        self.add_pin_list(self.get_ref_nets().split())

    def create_array(self):
        super().create_array()
        x_offset = OPTS.reference_cell_x
        if OPTS.num_bitcell_dummies % 2 == 1:
            mirror = MIRROR_Y_AXIS
            x_offset += self.ref_mux.width
        else:
            mirror = NO_MIRROR
        inst = self.add_inst("ref_mux", self.ref_mux, vector(x_offset, self.route_height),
                             mirror=mirror)
        self.connect_inst(self.get_ref_nets().split() + ["gnd"])

        for pin_name in ["bl", "br"]:

            for i in range(2):
                source_name = "{}<{}>".format(pin_name, i)
                dest_name = "ref_{}[{}]".format(pin_name, i)
                self.copy_layout_pin(inst, source_name, dest_name)

            pin = inst.get_pin("{}_out".format(pin_name))
            self.add_layout_pin("ref_{}_out".format(pin_name), pin.layer,
                                vector(pin.lx(), 0), width=pin.width(),
                                height=pin.by())
