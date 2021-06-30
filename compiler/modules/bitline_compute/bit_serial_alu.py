from base import utils
from base.contact import m2m3, m1m2, contact
from base.design import design
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.bitline_compute.bitline_alu import BitlineALU
from modules.bitline_compute.bl_bank import BlBank
from modules.logic_buffer import LogicBuffer
from tech import delay_strategy_class


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
    pin_names = []
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
        self.height = self.mcc_col.height

        self.route_layout()

    def add_pins(self):
        for col in range(self.num_cols):
            self.add_pin("data_in[{}]".format(col))
            self.add_pin("mask_in[{}]".format(col))
            self.add_pin("and_in[{}]".format(col))
            self.add_pin("nor_in[{}]".format(col))

        for col in range(self.num_cols):
            self.add_pin("bus_out[{}]".format(col))

        for col in range(self.num_cols):
            self.add_pin("mask_bar_out[{}]".format(col))

        for word in range(self.num_cols):
            # self.add_pin_list(["c_val[{}]".format(word)])
            self.add_pin_list(["c_val[{}]".format(word), "cin[{}]".format(word), "cout[{}]".format(word)])

        self.add_pin_list(["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor", "s_sum", "s_data_in", "s_cout",  # select data
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

        if OPTS.run_optimizations:
            delay_strategy = delay_strategy_class()(self.bank)
            sizes = delay_strategy.get_alu_clk_sizes()
        else:
            sizes = OPTS.sr_clk_buffers
        self.clk_buf = LogicBuffer(buffer_stages=sizes, logic="pnor2", height=OPTS.logic_buffers_height,
                                   contact_nwell=True, contact_pwell=True)

        self.add_mod(self.clk_buf)

    def route_layout(self):

        # get grid locations
        grid_pitch = self.m4_width + self.parallel_line_space
        self.m4_grid = [0.5 * self.m4_width + x * grid_pitch for x in range(6)]

        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            self.route_latch_clk()

        self.copy_layout_pins()

        self.route_vdd_gnd()
        self.route_sr_clk()
        self.add_poly_dummy()

    def add_modules(self):

        self.bank_x_shift = self.bank.bitcell_array_inst.lx()

        and_pin = self.bank.get_pin("and[0]")
        self.bank_y_shift = self.mcc_col.height - and_pin.by()

        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.num_cols)

        for col in range(self.num_cols):

            mcc_inst = self.add_inst("mcc{}".format(col), mod=self.mcc_col,
                                     offset=vector(self.bitcell_offsets[col]+self.bank_x_shift, self.mcc_col.height),
                                     mirror="MX")
            self.mcc_insts.append(mcc_inst)

            data_connections = "and_in[{col}] nor_in[{col}] data_in[{col}] mask_in[{col}] c_val[{col}] "\
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

        for x_offset in self.tap_offsets:
            self.add_inst(self.col_tap.name, self.col_tap, vector(x_offset+self.bank_x_shift, self.col_tap.height),
                          mirror="MX")
            self.connect_inst([])

        # add sr clk buffer
        self.add_clk_buf()

    def get_clk_buf_connections(self):
        return ["sr_en", "sr_clk", "sr_clk_buf", "sr_clk_bar", "vdd", "gnd"]

    def copy_layout_pins(self):
        pin_names = ("s_and s_data_in s_nand s_nor s_or s_xnor s_xor s_cout "
                     "s_add s_mask_in s_bus mask_en").split()

        for pin_name in pin_names:
            if pin_name == "mask_en":
                dest_pin = pin_name
                pin_name = "en_mask"
            else:
                dest_pin = pin_name
            pin = self.mcc_insts[0].get_pin(pin_name)

            self.add_layout_pin(dest_pin, pin.layer, offset=pin.ll(), height=pin.height(),
                                width=self.mcc_insts[-1].get_pin(pin_name).rx()-pin.lx())

        col_pins = ["cin", "cout", "c_val", "mask_bar_out", "data_in", "mask_in"]
        # col_pins = ["c_val", "mask_bar_out", "data_in", "mask_in"]

        for col in range(self.num_cols):
            for pin_name in col_pins:
                self.copy_layout_pin(self.mcc_insts[col], pin_name, pin_name+"[{}]".format(col))
            self.copy_layout_pin(self.mcc_insts[col], "out", "bus_out[{}]".format(col))

        self.copy_layout_pin(self.clk_buf_inst, "A", "sr_en")

    def route_sr_clk(self):

        # clk pin
        clk_pin = self.mcc_insts[0].get_pin("clk")
        out_pin = self.clk_buf_inst.get_pin("out")

        if out_pin.by() > clk_pin.by() and out_pin.uy() > clk_pin.uy():

            self.add_rect("metal1", offset=vector(out_pin.rx(), clk_pin.by()), width=clk_pin.lx()-out_pin.rx(),
                          height=clk_pin.height())

            # connect vdd
            vdd_pins = self.mcc_insts[0].get_pins("vdd")
            closest_vdd = min(filter(lambda x: x.uy() < clk_pin.by(), vdd_pins), key=lambda x: clk_pin.by() - x.by())

            buf_vdd = self.clk_buf_inst.get_pin("vdd")
            self.add_rect("metal1", offset=vector(buf_vdd.rx(), closest_vdd.by()),
                          width=closest_vdd.lx() - buf_vdd.rx(), height=closest_vdd.height())
            self.add_rect("metal1", offset=buf_vdd.lr(), width=buf_vdd.height(), height=closest_vdd.by() - buf_vdd.by())

            # connect gnd
            closest_gnd = min(filter(lambda x: x.by() > clk_pin.by(), self.mcc_insts[0].get_pins("gnd")),
                              key=lambda x: x.by() - clk_pin.by())

            buf_gnd = self.clk_buf_inst.get_pin("gnd")
            self.add_rect("metal1", offset=buf_gnd.lr(), width=buf_gnd.height(), height=closest_gnd.uy() - buf_gnd.by())
            self.add_rect("metal1", offset=vector(buf_gnd.rx(), closest_gnd.by()),
                          width=closest_gnd.lx() - buf_gnd.rx(), height=closest_gnd.height())

        else:
            buf_vdd = self.clk_buf_inst.get_pin("vdd")

            power_via = contact(m1m2.layer_stack, dimensions=[2, 1])

            # go down for vdd
            vdd_pins = self.mcc_insts[0].get_pins("vdd")
            closest_vdd = min(filter(lambda x: x.uy() < buf_vdd.by(), vdd_pins),
                              key=lambda x: abs(buf_vdd.by() - x.by()))

            self.add_rect("metal1", offset=buf_vdd.lr(), width=self.mid_vdd.cx() - buf_vdd.rx(),
                          height=buf_vdd.height())
            self.add_rect("metal1", offset=vector(self.mid_vdd.cx() - 0.5*power_via.height,
                                                  closest_vdd.cy()), height=buf_vdd.uy()-closest_vdd.cy(),
                          width=power_via.height)

            # go down for gnd
            buf_gnd = self.clk_buf_inst.get_pin("gnd")
            gnd_pins = self.mcc_insts[0].get_pins("gnd")
            closest_gnd = min(filter(lambda x: x.uy() > buf_gnd.uy(), gnd_pins),
                              key=lambda x: abs(x.by() - buf_gnd.uy()))

            self.add_rect("metal1", offset=buf_gnd.lr(), width=self.mid_gnd.cx() - buf_gnd.rx(),
                          height=buf_gnd.height())
            self.add_rect("metal1", offset=vector(self.mid_gnd.cx() - 0.5 * power_via.height,
                                                  buf_gnd.by()), height=closest_gnd.cy() - buf_gnd.cy(),
                          width=power_via.height)

            # avoid closest vdd or gnd pin
            closest_power = min(self.mcc_insts[0].get_pins("vdd") + self.mcc_insts[0].get_pins("gnd"),
                                key=lambda x: abs(clk_pin.cy() - x.cy()))

            x_bend = self.mid_gnd.rx() + self.wide_m1_space
            self.add_rect("metal1", offset=out_pin.ll(), width=x_bend-out_pin.lx())
            self.add_rect("metal1", offset=vector(x_bend, out_pin.by()), height=clk_pin.uy()-out_pin.by())
            self.add_rect("metal1", offset=vector(x_bend, clk_pin.by()), width=clk_pin.lx()-x_bend,
                          height=clk_pin.height())

        # clk in
        clk_in = self.clk_buf_inst.get_pin("B")
        bank_clk = self.bank.get_pin("clk")
        self.add_contact(m2m3.layer_stack, offset=clk_in.ul())
        y_offset = clk_in.uy() + m2m3.height
        x_bend = self.mid_vdd.lx() - self.wide_m1_space - self.m3_width

        self.add_rect("metal3", offset=vector(clk_in.lx(), y_offset), width=x_bend-clk_in.lx())

        y_bend = self.mcc_insts[0].uy() + self.line_end_space
        self.add_rect("metal3", offset=vector(x_bend, y_offset), height=y_bend-y_offset)
        self.add_rect("metal3", offset=vector(x_bend, y_bend), width=bank_clk.lx()-x_bend)

        self.add_contact(m2m3.layer_stack, offset=vector(bank_clk.lx()+self.m2_width, y_bend), rotate=90)
        self.add_rect("metal2", offset=vector(bank_clk.lx(), y_bend),
                      height=bank_clk.by() + self.bank_y_shift - y_bend)
