from base import design
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.single_level_column_mux_array import single_level_column_mux_array


@library_import
class tgate_column_mux_tap(design.design):
    pin_names = []
    lib_name = getattr(OPTS, "tgate_column_mux_tap_mod", "tgate_column_mux_tap")


@library_import
class tgate_column_mux(design.design):
    pin_names = "bl br bl_out br_out sel gnd vdd".split()
    lib_name = getattr(OPTS, "tgate_column_mux_mod", "tgate_column_mux")


class tgate_column_mux_array(single_level_column_mux_array):

    def create_layout(self):
        super().create_layout()
        self.add_body_contacts()

    def create_modules(self):
        self.mux = tgate_column_mux()
        self.child_mod = self.mux
        self.add_mod(self.mux)
        if OPTS.use_x_body_taps:
            self.body_tap = tgate_column_mux_tap()

    def connect_inst(self, args, check=True):
        if "gnd" in args:
            args.append("vdd")
        super().connect_inst(args, check)

    def add_layout_pins(self):
        super().add_layout_pins()
        for pin_name in ["vdd"]:
            for pin in self.child_insts[0].get_pins(pin_name):
                self.add_layout_pin(pin_name, pin.layer, offset=vector(0, pin.by()),
                                    width=self.child_insts[-1].rx(), height=pin.height())

    def add_body_contacts(self):
        y_offset = self.child_insts[0].by()
        for x_offset in self.tap_offsets:
            self.add_inst(name=self.body_tap.name, mod=self.body_tap, offset=vector(x_offset, y_offset))
            self.connect_inst([])

    def add_pins(self):
        super().add_pins()
        self.add_pin("vdd")