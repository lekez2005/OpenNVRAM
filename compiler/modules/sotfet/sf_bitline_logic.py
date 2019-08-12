from base.design import design
from base.library_import import library_import


@library_import
class SfBitlineLogic(design):
    """
    Combine data and mask and operation to implement data_out for write driver module
    search pin: 0 indicates write operation, 1 indicates search operation
    data pin: data to be written or searched
    mask pin: 1 indicates search/write this column
    logic operation: bl = search_cbar.mask.data + write_bar.mask_bar + write_bar.data
    logic operation: br = search_cbar.mask.data_bar + write_bar.mask_bar + write_bar.data_barc
    subckt def: .SUBCKT sot_bitline_logic write_bar search_cbar data data_bar mask mask_bar bl br vdd gnd
    """
    pin_names = ["write_bar", "search_cbar", "data", "data_bar", "mask", "mask_bar", "bl", "br", "vdd", "gnd"]
    lib_name = "sot_bitline_logic"
