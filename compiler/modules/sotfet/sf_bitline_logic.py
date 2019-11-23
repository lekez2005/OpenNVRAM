from base.design import design
from base.library_import import library_import


@library_import
class SfBitlineLogic(design):
    """
    Combine data and mask and operation to implement data_out for write driver module
    search pin: 0 indicates write operation, 1 indicates search operation
    data pin: data to be written or searched
    mask pin: 1 indicates search/write this column
    logic operation: bl = en.mask.data
    logic operation: br = en.mask.data_bar
    subckt def: .SUBCKT sot_bitline_logic data data_bar mask mask_bar en bl br vdd gnd
    """
    pin_names = ["en", "data", "data_bar", "mask", "bl", "br", "vdd", "gnd"]
    lib_name = "sot_bitline_logic"
