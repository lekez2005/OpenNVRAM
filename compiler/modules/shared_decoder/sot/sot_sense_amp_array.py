from base.design import design
from base.geometry import MIRROR_Y_AXIS, NO_MIRROR
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.sense_amp_array import sense_amp_array


@library_import
class sot_sense_amp(design):
    pin_names = "bl br dout_bar en en_bar gnd vclamp vdd vref".split()
    lib_name = OPTS.sense_amp_mod


@library_import
class sot_sense_ref(design):
    pin_names = "bl_zero br_zero bl_one br_one en_bar vclamp vref".split()
    lib_name = OPTS.sense_amp_ref


class SotSenseAmpArray(sense_amp_array):
    @property
    def bus_pins(self):
        return ["bl", "br", "dout", "dout_bar"]

    def add_pins(self):
        super().add_pins()

    def create_array(self):
        super().create_array()
        self.sense_ref = sot_sense_ref()
        self.add_mod(self.sense_ref)

        x_offset = OPTS.reference_cell_x
        if OPTS.num_dummies % 2 == 1:
            mirror = MIRROR_Y_AXIS
            x_offset += self.sense_ref.width
        else:
            mirror = NO_MIRROR
        inst = self.add_inst("ref_mux", self.sense_ref, vector(x_offset, 0),
                             mirror=mirror)
        self.sense_ref_inst = inst
        self.connect_inst("ref_bl[0] ref_bl[1] en_bar vclamp vref vdd gnd".split())

    def add_layout_pins(self):
        super().add_layout_pins()
        self.add_pin_list(["ref_bl[0]", "ref_br[0]", "ref_bl[1]", "ref_br[1]"])
        self.copy_layout_pin(self.sense_ref_inst, "bl_zero", "ref_bl[0]")
        self.copy_layout_pin(self.sense_ref_inst, "br_zero", "ref_br[0]")
        self.copy_layout_pin(self.sense_ref_inst, "bl_one", "ref_bl[1]")
        self.copy_layout_pin(self.sense_ref_inst, "br_one", "ref_br[1]")
