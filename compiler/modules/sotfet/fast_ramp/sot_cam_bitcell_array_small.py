from modules.sotfet.sf_cam_bitcell_array import sf_cam_bitcell_array


class sot_cam_bitcell_array_small(sf_cam_bitcell_array):
    """
    Creates a rows x cols array of memory cells. Assumes bit-lines
    and word line is connected by abutment.
    Connects the word lines and bit lines.
    """

    def connect_inst(self, args, check=True):
        if len(args) > 0 and args[0].startswith("bl"):
            args = args[:4] + args[5:]
        super().connect_inst(args, check)
