from modules import bitcell


class cam_bitcell(bitcell.bitcell):
    """
    A single CAM bit cell (6T, 8T, etc.)  This module implements the
    single memory cell used in the design. It is a hand-made cell, so
    the layout and netlist should be available in the technology
    library.
    """
    pin_names = ["BL", "BR", "WL", "ML", "vdd", "gnd"]
