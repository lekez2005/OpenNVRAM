from base.design import design
from base.library_import import library_import


@library_import
class current_mirror(design):
    """
    wordline driver
    """
    pin_names = "vbias_n vbias_p vdd gnd".split()
    lib_name = "current_mirror"
