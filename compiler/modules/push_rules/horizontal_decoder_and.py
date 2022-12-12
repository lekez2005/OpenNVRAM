from base.design import design
from base.library_import import library_import


@library_import
class and2(design):
    pin_names = "A_bar<0> A_bar<1> B en gnd vdd wl<0> wl<1>".split()
    lib_name = "push_rules/decoder_and2"


@library_import
class and2_tap(design):
    pin_names = ["vdd", "gnd"]
    lib_name = "push_rules/decoder_and2_tap"


@library_import
class and3(design):
    pin_names = "A_bar<0> A_bar<1> B C en gnd vdd wl<0> wl<1>".split()
    lib_name = "push_rules/decoder_and3"


@library_import
class and3_tap(design):
    pin_names = ["vdd", "gnd"]
    lib_name = "push_rules/decoder_and3_tap"
