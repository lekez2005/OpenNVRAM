from base.design import design
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.bitline_compute.bitline_alu import BitlineALU
from modules.bitline_compute.bl_bank import BlBank


@library_import
class col_bs(design):
    """
    Contains bit serial col cin and cout
    and_in nor_in data_in mask_in cin clk S cout out mask_bar_out
    s_and s_nand s_or s_nor s_xor s_xnor s_sum s_data_in vdd gnd
    """
    pin_names = "and_in nor_in data_in mask_in c_val " \
                "s_cout s_and s_data_in s_nand s_nor s_or s_xnor s_xor s_add s_mask_in s_bus " \
                "out mask_bar_out clk latch_clk en_mask vdd gnd".split()
    lib_name = "col_bs"


@library_import
class col_bs_tap(design):
    """
    """
    pin_names = []
    lib_name = "col_bs_tap"


@library_import
class sa_col_bs(design):
    """
    Contains bit serial col cin and cout
    and_in nor_in data_in mask_in cin clk S cout out mask_bar_out
    s_and s_nand s_or s_nor s_xor s_xnor s_sum s_data_in vdd gnd
    """
    pin_names = "and_in nor_in data_in mask_in c_val " \
                "s_cout s_and s_data_in s_nand s_nor s_or s_xnor s_xor s_add s_mask_in s_bus " \
                "out mask_bar_out cin cout clk en_mask vdd gnd".split()
    lib_name = "sa_col_bs"


@library_import
class sa_col_bs_tap(design):
    """
    """
    pin_names = ["vdd", "gnd"]
    lib_name = "sa_col_bs_tap"


class BitSerialALU(BitlineALU):
    mcc_col = col_tap = None

    clk_buf = clk_buf_inst = None

    mcc_insts = []

    def __init__(self, bank, num_cols):
        design.__init__(self, "alu_{}".format(num_cols))
        self.num_cols = num_cols
        self.bank = bank  # type: BlBank

        self.add_pins()
        self.create_modules()
        self.add_modules()

        self.width = self.mcc_insts[-1].rx()

        self.route_layout()

    def add_pins(self):
        self.add_common_alu_pins()

        for word in range(self.num_cols):
            # self.add_pin_list(["c_val[{}]".format(word)])
            self.add_pin_list(["c_val[{}]".format(word), "cin[{}]".format(word),
                               "cout[{}]".format(word)])

        self.add_pin_list(["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor", "s_sum",
                           "s_data_in", "s_cout",  # select data
                           "s_mask_in", "s_bus"])  # mask select
        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            self.add_pin_list(["mask_en", "sr_en", "latch_clk", "sr_clk", "vdd", "gnd"])
        else:
            self.add_pin_list(["mask_en", "sr_en", "sr_clk", "vdd", "gnd"])

    def create_modules(self):
        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            self.mcc_col = col_bs()
            self.add_mod(self.mcc_col)

            self.col_tap = col_bs_tap()
            self.add_mod(self.col_tap)
        else:
            self.mcc_col = sa_col_bs()
            self.add_mod(self.mcc_col)

            self.col_tap = sa_col_bs_tap()
            self.add_mod(self.col_tap)
        self.height = self.mcc_col.height
        self.create_clk_buf("pnor2")
        self.calculate_fill_widths()

    def route_msb_lsb(self):
        pass

    def route_shift_ins(self):
        pass

    def route_carries(self):
        pass

    def add_modules(self):

        x_offsets, tap_offsets = self.calculate_bank_offsets()

        for col in range(self.num_cols):

            mcc_inst = self.add_inst("mcc{}".format(col), mod=self.mcc_col,
                                     offset=vector(x_offsets[col],
                                                   self.mcc_col.height),
                                     mirror="MX")
            self.mcc_insts.append(mcc_inst)

            data_connections = "and_in[{col}] nor_in[{col}] data_in[{col}] mask_in[{col}] c_val[{col}] " \
                .format(col=col).split()
            select_connections = "s_cout s_and s_data_in s_nand s_nor s_or s_xnor s_xor s_sum " \
                                 "s_mask_in s_bus".split()

            if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
                other_connections = ["bus_out[{}]".format(col), "mask_bar_out[{}]".format(col), "cin[{}]".format(col),
                                     "cout[{}]".format(col), "latch_clk", "sr_clk_buf", "mask_en", "vdd", "gnd"]
            else:
                other_connections = ["bus_out[{}]".format(col), "mask_bar_out[{}]".format(col), "cin[{}]".format(col),
                                     "cout[{}]".format(col), "sr_clk_buf", "mask_en", "vdd", "gnd"]

            self.connect_inst(data_connections + select_connections + other_connections)

        for x_offset in tap_offsets:
            self.add_inst(self.col_tap.name, self.col_tap, vector(x_offset + self.bank_x_shift, self.col_tap.height),
                          mirror="MX")
            self.connect_inst([])
            self.copy_layout_pin(self.insts[-1], "vdd")
            self.copy_layout_pin(self.insts[-1], "gnd")

        # add sr clk buffer
        self.add_clk_buf()

    def get_clk_buf_connections(self):
        return ["sr_clk", "sr_en", "sr_clk_buf", "sr_clk_bar", "vdd", "gnd"]

    def copy_layout_pins(self):
        pin_names = ("s_and s_data_in s_nand s_nor s_or s_xnor s_xor s_cout "
                     "s_add s_mask_in s_bus mask_en").split()

        for pin_name in pin_names:
            if pin_name == "mask_en":
                dest_pin = pin_name
                pin_name = "en_mask"
            elif pin_name == "s_add":
                dest_pin = "s_sum"
            else:
                dest_pin = pin_name
            pin = self.mcc_insts[0].get_pin(pin_name)

            self.add_layout_pin(dest_pin, pin.layer, offset=pin.ll(), height=pin.height(),
                                width=self.mcc_insts[-1].get_pin(pin_name).rx() - pin.lx())

        col_pins = ["cin", "cout", "c_val", "mask_bar_out", "data_in", "mask_in",
                    "and_in", "nor_in"]
        # col_pins = ["c_val", "mask_bar_out", "data_in", "mask_in"]

        for col in range(self.num_cols):
            for pin_name in col_pins:
                self.copy_layout_pin(self.mcc_insts[col], pin_name, pin_name + "[{}]".format(col))
            self.copy_layout_pin(self.mcc_insts[col], "out", "bus_out[{}]".format(col))

        self.copy_layout_pin(self.clk_buf_inst, "B", "sr_en")
