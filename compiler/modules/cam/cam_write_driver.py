from base import design
from base.library_import import library_import


@library_import
class cam_write_driver(design.design):
    """
    write driver to be active during write operations only.
    This module implements the write driver cell used in the design. It
    is a hand-made cell, so the layout and netlist should be available in
    the technology library.
    """
    lib_name = "cam_write_driver"

