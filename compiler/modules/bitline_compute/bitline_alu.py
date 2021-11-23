import debug
from base import utils
from base.contact import m1m2, m2m3, m3m4, cross_m2m3, cross_m3m4, cross_m1m2
from base.design import design, METAL3, METAL4, METAL2, METAL1
from base.layout_clearances import get_range_overlap
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.bitline_compute.bl_bank import BlBank
from modules.logic_buffer import LogicBuffer
from tech import delay_strategy_class
from tech import drc


@library_import
class mcc_col(design):
    """
    Contains mcc col for cin and cout
    and_in nor_in data_in mask_in cin clk S cout out mask_bar_out
    s_and s_nand s_or s_nor s_xor s_xnor s_sum s_data_in vdd gnd
    """
    pin_names = "and_in nor_in data_in mask_in shift_in msb lsb cin " \
                "s_and s_data_in s_nand s_nor s_or s_xnor s_xor s_add" \
                " s_mask_in s_bus s_shft s_sr s_lsb s_msb " \
                "coutb out mask_bar_out shift_out latch_clk clk vdd gnd".split()
    lib_name = "col"


@library_import
class mcc_col_bar(design):
    """
    Contains mcc col for cinb and coutb
    """
    pin_names = "and_in nor_in data_in mask_in shift_in msb lsb cinb " \
                "s_and s_data_in s_nand s_nor s_or s_xnor s_xor s_add" \
                " s_mask_in s_bus s_shft s_sr s_lsb s_msb " \
                "cout out mask_bar_out shift_out latch_clk clk vdd gnd".split()
    lib_name = "colb"


@library_import
class col_tap(design):
    """
    Contains mcc col for cinb and coutb
    """
    pin_names = []
    lib_name = "col_tap"


@library_import
class sa_col(design):
    """
    Contains mcc col for cin and cout
    and_in nor_in data_in mask_in cin clk S cout out mask_bar_out
    s_and s_nand s_or s_nor s_xor s_xnor s_sum s_data_in vdd gnd
    """
    pin_names = "and_in nor_in data_in mask_in shift_in msb lsb cin " \
                "s_and s_data_in s_nand s_nor s_or s_xnor s_xor s_add" \
                " s_mask_in s_bus s_shft s_sr s_lsb s_msb " \
                "coutb out mask_bar_out shift_out clk vdd gnd".split()
    lib_name = "sa_col"


@library_import
class sa_col_bar(design):
    """
    Contains mcc col for cinb and coutb
    """
    pin_names = "and_in nor_in data_in mask_in shift_in msb lsb cinb " \
                "s_and s_data_in s_nand s_nor s_or s_xnor s_xor s_add" \
                " s_mask_in s_bus s_shft s_sr s_lsb s_msb " \
                "cout out mask_bar_out shift_out clk vdd gnd".split()
    lib_name = "sa_colb"


@library_import
class sa_col_tap(design):
    """
    Contains mcc col for cinb and coutb
    """
    pin_names = []
    lib_name = "sa_col_tap"


class BitlineALU(design):
    mcc_col = mcc_col_bar = col_tap = flop = None

    clk_buf = clk_buf_inst = None

    mcc_insts = []

    def __init__(self, bank: BlBank, num_cols, word_size, cells_per_group, inverter_size=1):
        super().__init__("alu_{}".format(num_cols))
        self.num_cols = num_cols
        self.inverter_size = inverter_size
        self.word_size = word_size
        self.num_words = int(num_cols / word_size)
        self.bank = bank

        assert word_size % cells_per_group == 0, "Number of cells per group should be a factor of word size to even out"

        self.add_pins()
        self.create_modules()
        self.add_modules()

        self.width = self.mcc_insts[-1].rx()

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

        for word in range(self.num_words):
            self.add_pin_list(["cin[{}]".format(word), "cout[{}]".format(word)])

        self.add_pin_list(["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor",
                           "s_sum", "s_data_in",  # select data
                           "s_mask_in", "s_bus", "s_shift", "s_sr", "s_lsb", "s_msb"])  # mask select
        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            self.add_pin_list(["sr_en", "latch_clk", "sr_clk", "vdd", "gnd"])
        else:
            self.add_pin_list(["sr_en", "sr_clk", "vdd", "gnd"])
        debug.info(2, "ALU pins: %s", self.pins)

    def create_modules(self):

        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            self.mcc_col = mcc_col()
            self.add_mod(self.mcc_col)
            self.mcc_col_bar = mcc_col_bar()
            self.add_mod(self.mcc_col_bar)

            self.col_tap = col_tap()
            self.add_mod(self.col_tap)
        else:
            self.mcc_col = sa_col()
            self.add_mod(self.mcc_col)
            self.mcc_col_bar = sa_col_bar()
            self.add_mod(self.mcc_col_bar)

            self.col_tap = sa_col_tap()
            self.add_mod(self.col_tap)

        self.height = self.mcc_col.height

        if OPTS.run_optimizations:
            delay_strategy = delay_strategy_class()(self.bank)
            sizes = delay_strategy.get_alu_clk_sizes()
        else:
            sizes = OPTS.sr_clk_buffers
        self.clk_buf = LogicBuffer(buffer_stages=sizes, logic="pnand2",
                                   height=OPTS.logic_buffers_height,
                                   route_outputs=False,
                                   contact_nwell=True, contact_pwell=True)

        self.add_mod(self.clk_buf)

        self.m3_fill_width = self.bank.mid_vdd.width()
        _, self.m3_fill_height = self.calculate_min_area_fill(self.m3_fill_width,
                                                              layer=METAL3)

    def route_layout(self):

        # get grid locations
        grid_pitch = self.m4_width + self.parallel_line_space
        self.m4_grid = [0.5 * self.m4_width + x * grid_pitch for x in range(6)]

        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            self.route_latch_clk()

        self.copy_layout_pins()
        self.add_poly_dummy()

        self.route_msb_lsb()
        self.route_shift_ins()
        self.route_carries()
        self.route_vdd_gnd()
        self.route_sr_clk()

    def add_modules(self):
        self.bank_x_shift = self.bank.bitcell_array_inst.lx()

        and_pin = self.bank.get_pin("and[0]")
        self.bank_y_shift = self.mcc_col.height - and_pin.by()

        self.bitcell_offsets = self.bank.bitcell_array.bitcell_offsets
        x_offsets = [self.bank_x_shift + x for x in self.bitcell_offsets]
        tap_offsets = self.bank.bitcell_array.tap_offsets

        current_word = 0
        for col in range(self.num_cols):
            # col and colb differences
            if col % 2 == 0:
                current_cell = self.mcc_col
                carry_out_template = "coutb_int[{}]"
                cin_template = "cout_int[{}]"
            else:
                current_cell = self.mcc_col_bar
                carry_out_template = "cout_int[{}]"
                cin_template = "coutb_int[{}]"

            mcc_inst = self.add_inst("mcc{}".format(col), mod=current_cell,
                                     offset=vector(x_offsets[col], current_cell.height),
                                     mirror="MX")
            self.mcc_insts.append(mcc_inst)

            shift_in = "shift_out[{}]".format(col + 1)
            shift_out = "shift_out[{}]".format(col)

            msb_in = "shift_out[{}]".format((current_word + 1) * self.word_size - 1)
            lsb_in = "shift_out[{}]".format(current_word * self.word_size)

            cin = cin_template.format(col - 1)
            cout = carry_out_template.format(col)

            if col % self.word_size == 0:
                cin = "cin[{}]".format(current_word)
            elif col % self.word_size == (self.word_size - 1):
                shift_in = "gnd"
                cout = "cout[{}]".format(current_word)

            data_connections = "and_in[{col}] nor_in[{col}] data_in[{col}] mask_in[{col}] {shift_in} " \
                               " {msb_in} {lsb_in} {cin} ".format(col=col, shift_in=shift_in, msb_in=msb_in,
                                                                  lsb_in=lsb_in, cin=cin).split()
            select_connections = "s_and s_data_in s_nand s_nor s_or s_xnor s_xor s_sum " \
                                 "s_mask_in s_bus s_shift s_sr s_lsb s_msb".split()

            if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
                other_connections = [cout, "bus_out[{}]".format(col), "mask_bar_out[{}]".format(col),
                                     shift_out, "latch_clk", "sr_clk_buf", "vdd", "gnd"]
            else:
                other_connections = [cout, "bus_out[{}]".format(col), "mask_bar_out[{}]".format(col),
                                     shift_out, "sr_clk_buf", "vdd", "gnd"]

            self.connect_inst(data_connections + select_connections + other_connections)

            if col % self.word_size == (self.word_size - 1):
                current_word += 1

        tap_offsets = [x + self.bank_x_shift for x in tap_offsets]
        for x_offset in tap_offsets:
            self.add_inst(self.col_tap.name, self.col_tap,
                          vector(x_offset, self.col_tap.height),
                          mirror="MX")
            self.connect_inst([])

        # add sr clk buffer
        self.add_clk_buf()

    def get_clk_buf_connections(self):
        return ["sr_en", "sr_clk", "sr_clk_bar", "sr_clk_buf", "vdd", "gnd"]

    def add_clk_buf(self):
        sr_clk = self.mcc_insts[0].get_pin("clk")

        vdd_pins = self.mcc_insts[0].get_pins("vdd")
        closest_vdd = min(filter(lambda x: x.uy() < sr_clk.by(), vdd_pins), key=lambda x: sr_clk.by() - x.by())

        clk_y = self.bank.cross_clk_rail.by() + self.mcc_col.height

        y_offset = min(closest_vdd.cy() + self.clk_buf.height,
                       clk_y - self.rail_height - self.wide_m1_space)

        x_offset = self.bank.mid_vdd.lx() - self.wide_m1_space - self.clk_buf.width

        self.clk_buf_inst = self.add_inst("clk_buf", mod=self.clk_buf,
                                          offset=vector(x_offset, y_offset), mirror="MX")

        self.connect_inst(self.get_clk_buf_connections())

    def route_latch_clk(self):
        bank_clk_pin = self.bank.control_buffers_inst.get_pin("clk_buf")
        latch_clk_pins = self.mcc_insts[0].get_pins("latch_clk")

        top_clk_pin = max(latch_clk_pins, key=lambda x: x.uy())
        bot_clk_pin = min(latch_clk_pins, key=lambda x: x.by())

        instances_x_diff = [x.lx() - bank_clk_pin.lx() for x in self.mcc_insts]

        valid_pins = list(filter(lambda x: x > 0, instances_x_diff))
        if len(valid_pins) > 0:
            closest_x = min(valid_pins) + bank_clk_pin.lx()
        else:
            closest_x = bank_clk_pin.lx()
            self.add_rect("metal1", offset=top_clk_pin.lr(), width=closest_x - top_clk_pin.rx())
            self.add_rect("metal1", offset=bot_clk_pin.lr(), width=self.m4_grid[4] + closest_x - bot_clk_pin.rx())

        bank_pin_y = bank_clk_pin.by() + self.bank_y_shift

        bend_y = top_clk_pin.cy() + self.line_end_space + 0.5 * m2m3.height + 0.5 * m1m2.height
        self.add_rect("metal2", offset=vector(bank_clk_pin.lx(), bend_y),
                      height=bank_pin_y - bend_y)

        self.add_contact(m1m2.layer_stack, offset=vector(bank_clk_pin.lx(),
                                                         bend_y + 0.5 * (self.m3_width - m1m2.height)))
        self.add_rect("metal1", offset=vector(bank_clk_pin.lx(), top_clk_pin.by()),
                      height=bend_y - top_clk_pin.by())

        rail_x = closest_x + self.m4_grid[4]

        fill_height = cross_m3m4.height
        _, m2_fill_width = self.calculate_min_area_fill(fill_height, layer=METAL2)
        _, m3_fill_width = self.calculate_min_area_fill(fill_height, layer=METAL3)

        for pin in [top_clk_pin, bot_clk_pin]:
            offset = vector(rail_x + 0.5 * self.m4_width, pin.cy())
            self.add_cross_contact_center(cross_m1m2, offset, rotate=True)
            self.add_cross_contact_center(cross_m2m3, offset)
            self.add_cross_contact_center(cross_m3m4, offset, rotate=True)
            self.add_rect_center(METAL2, offset, width=m2_fill_width, height=fill_height)
            self.add_rect_center(METAL3, offset, width=m3_fill_width, height=fill_height)
        self.add_rect(METAL4, offset=vector(rail_x, bot_clk_pin.by()),
                      height=top_clk_pin.cy() - bot_clk_pin.cy())

        self.add_layout_pin("latch_clk", top_clk_pin.layer, offset=top_clk_pin.ll(),
                            width=self.mcc_insts[-1].get_pins("latch_clk")[0].rx() - top_clk_pin.lx())

    def copy_layout_pins(self):
        source_names = ("s_and s_data_in s_nand s_nor s_or s_xnor s_xor "
                        "s_add s_mask_in s_bus s_shft s_sr s_lsb s_msb ").split()

        for pin_name in source_names:
            pin = self.mcc_insts[0].get_pin(pin_name)
            dest_pin = pin_name
            if pin_name == "s_shft":
                dest_pin = "s_shift"
            elif pin_name == "s_add":
                dest_pin = "s_sum"
            self.add_layout_pin(dest_pin, pin.layer, offset=pin.ll(), height=pin.height(),
                                width=self.mcc_insts[-1].get_pin(pin_name).rx() - pin.lx())

        for i in range(self.num_words):
            col = i * self.word_size
            self.copy_layout_pin(self.mcc_insts[col], "cin", "cin[{}]".format(i))

        for i in range(self.num_words):
            col = (i + 1) * self.word_size - 1
            self.copy_layout_pin(self.mcc_insts[col], "cout", "cout[{}]".format(i))

        pin_combinations = [("out", "bus_out"), "mask_bar_out", "data_in",
                            "mask_in", "and_in", "nor_in"]

        for col in range(self.num_cols):
            for pin in pin_combinations:
                if isinstance(pin, str):
                    source_name, dest_name = pin, pin
                else:
                    source_name, dest_name = pin
                self.copy_layout_pin(self.mcc_insts[col], source_name, f"{dest_name}[{col}]")

        self.copy_layout_pin(self.clk_buf_inst, "A", "sr_en")

    def route_msb_lsb(self):
        for i in range(self.num_words):
            col = i * self.word_size
            msb_index = col + self.word_size - 1
            for pin_name in ["msb", "lsb"]:
                first_pin = self.mcc_insts[col].get_pin(pin_name)
                last_pin = self.mcc_insts[msb_index].get_pin(pin_name)
                self.add_rect(first_pin.layer, offset=first_pin.ll(), width=last_pin.rx() - first_pin.lx(),
                              height=first_pin.height())

                # connect
                if pin_name == "lsb":
                    source_pins = self.mcc_insts[col].get_pins("shift_out")
                else:
                    source_pins = self.mcc_insts[msb_index].get_pins("shift_out")
                source_pin = list(filter(lambda x: x.layer == "metal4", source_pins))[0]

                self.add_contact(m3m4.layer_stack,
                                 offset=vector(source_pin.rx(), first_pin.by()), rotate=90)

    def route_shift_ins(self):
        for word in range(self.num_words):
            for i in range(self.word_size - 1):
                col = word * self.word_size + i
                next_col = col + 1

                shift_out = list(filter(lambda x: x.layer == "metal3",
                                        self.mcc_insts[next_col].get_pins("shift_out")))[0]
                shift_in = self.mcc_insts[col].get_pin("shift_in")

                self.add_rect("metal3", offset=vector(shift_in.rx(), shift_out.by()),
                              width=shift_out.lx() - shift_in.rx(), height=shift_out.height())

            # msb shift in to gnd
            gnd_pins = self.mcc_insts[0].get_pins("gnd")
            col = word * self.word_size + self.word_size - 1
            shift_in = self.mcc_insts[col].get_pin("shift_in")

            closest_gnd = min(filter(lambda x: x.by() < shift_in.by(), gnd_pins),
                              key=lambda x: shift_in.by() - x.by())
            self.add_rect("metal3", offset=vector(shift_in.rx() - self.m3_width, closest_gnd.cy()),
                          height=shift_in.by() - closest_gnd.cy())

            fill_width = utils.ceil(drc["minarea_metal3_drc"] / m2m3.height)
            x_offset = shift_in.rx() - 0.5 * (self.m3_width + fill_width)
            y_offset = closest_gnd.cy() - 0.5 * m2m3.height
            self.add_rect("metal2", offset=vector(x_offset, y_offset), width=fill_width, height=m2m3.height)
            self.add_contact_center(m2m3.layer_stack, offset=vector(shift_in.rx() - 0.5 * self.m2_width,
                                                                    closest_gnd.cy()))
            self.add_contact_center(m1m2.layer_stack, size=[2, 1],
                                    offset=vector(shift_in.rx() - 0.5 * self.m2_width, closest_gnd.cy()))

    def route_carries(self):
        for word in range(self.num_words):
            for i in range(self.word_size):
                col = word * self.word_size + i
                if i == 0:
                    self.copy_layout_pin(self.mcc_insts[col], "cin", "cin[{}]".format(word))
                else:
                    if i % 2 == 0:
                        prev_cout = self.mcc_insts[col - 1].get_pin("cout")
                        cin = self.mcc_insts[col].get_pin("cin")
                    else:
                        prev_cout = self.mcc_insts[col - 1].get_pin("coutb")
                        cin = self.mcc_insts[col].get_pin("cinb")
                    self.add_rect(cin.layer, offset=prev_cout.lr(),
                                  width=cin.lx() - prev_cout.rx())

    def route_sr_clk(self):

        self.route_power_pin(self.clk_buf_inst.get_pin("vdd"), self.mid_vdd)
        self.route_power_pin(self.clk_buf_inst.get_pin("gnd"), self.mid_gnd)

        # clk pin
        clk_pin = self.mcc_insts[0].get_pin("clk")
        out_pin = self.clk_buf_inst.get_pin("out")
        self.add_rect("metal1", offset=vector(out_pin.lx(), clk_pin.by()), width=clk_pin.lx() - out_pin.lx(),
                      height=clk_pin.height())

        buffer_center_y = 0.5 * (self.clk_buf_inst.uy() + self.clk_buf_inst.by())
        self.add_rect("metal1", offset=vector(out_pin.lx(), buffer_center_y), width=out_pin.width(),
                      height=clk_pin.cy() - buffer_center_y)

        # clk in
        clk_in = self.clk_buf_inst.get_pin("B")
        bank_clk = self.bank.cross_clk_rail

        real_y_offset = bank_clk.by() + self.bank_y_shift
        via_extension = 0.5 * m2m3.height
        if bank_clk.lx() > clk_in.lx():
            x_start = min(clk_in.cx() - via_extension, bank_clk.lx())
            x_end = bank_clk.rx()
        else:
            x_start = bank_clk.lx()
            x_end = max(clk_in.cx() + via_extension, bank_clk.rx())
        self.add_layout_pin("sr_clk", METAL3, vector(x_start, real_y_offset),
                            width=x_end - x_start, height=bank_clk.height)
        self.add_rect(METAL2, clk_in.ul(), width=clk_in.width(),
                      height=real_y_offset - clk_in.uy())
        mid_y = real_y_offset + 0.5 * bank_clk.height
        self.add_cross_contact_center(cross_m2m3, vector(clk_in.cx(), mid_y))

    def route_vdd_gnd(self):
        # M2 rail
        layout_names = ["vdd", "gnd", "vdd", "gnd"]
        rail_names = ["mid_vdd", "mid_gnd", "right_vdd", "right_gnd"]
        m2_pins = [None] * 4
        for i in range(4):
            rail = getattr(self.bank, rail_names[i])

            pin = self.add_layout_pin(layout_names[i], rail.layer,
                                      offset=vector(rail.lx(), 0),
                                      width=rail.width(), height=self.height)
            self.add_rect(METAL4, pin.ll(), width=pin.width(), height=pin.height())
            m2_pins[i] = pin
        self.mid_vdd, self.mid_gnd, self.right_vdd, self.right_gnd = m2_pins

        for pin_name in ["vdd", "gnd"]:
            power_rail = getattr(self, f"right_{pin_name}")
            for pin in self.mcc_insts[-1].get_pins(pin_name):
                self.route_power_pin(pin, power_rail)
        self.route_left_mcc_power()

    def route_left_mcc_power(self):
        existing_pins = set()
        # get collisions
        for pin_name in ["vdd", "gnd"]:
            buffer_pin = self.clk_buf_inst.get_pin(pin_name)
            existing_pins.add((pin_name, buffer_pin.by(), buffer_pin.uy()))
            for _, _, flop_inst in self.bank.control_flop_insts:
                for pin in flop_inst.get_pins(pin_name):
                    existing_pins.add((pin_name, pin.by() + self.bank_y_shift,
                                       pin.uy() + self.bank_y_shift))

        wide_space = self.get_wide_space(METAL1)

        existing_pins = [(x[0], x[1] - wide_space, x[2] + wide_space, 0.5 * (x[1] + x[2]))
                         for x in existing_pins]

        for pin_name in ["vdd", "gnd"]:
            rail = getattr(self, f"mid_{pin_name}")
            pins = sorted(self.mcc_insts[0].get_pins(pin_name), key=lambda x: x.by())
            for pin in pins:
                closest_pin = min(existing_pins, key=lambda x: abs(x[3] - pin.cy()))
                if not get_range_overlap(closest_pin[1:3], (pin.by(), pin.uy())):
                    self.route_power_pin(pin, rail)
                else:
                    if closest_pin[0] == pin_name or pin_name == "gnd":
                        # same pin so direct route
                        offset = vector(rail.rx() - pin.height(), pin.by())
                        self.add_rect(METAL1, offset, height=pin.height(),
                                      width=pin.lx() - offset.x)
                        self.add_rect(METAL1, offset, width=pin.height(),
                                      height=closest_pin[3] - offset.y)

                    else:
                        x_offset = self.mid_gnd.rx() + self.get_parallel_space(METAL1)
                        y_offset = closest_pin[2]
                        offset = vector(x_offset, pin.by())
                        self.add_rect(METAL1, offset, width=pin.lx() - x_offset,
                                      height=pin.height())
                        self.add_rect(METAL1, offset, height=y_offset - offset.y)
                        rect = self.add_rect(METAL1, vector(x_offset, y_offset),
                                             width=self.m1_width, height=pin.height())
                        self.route_power_pin(rect, rail)

    def route_power_pin(self, pin, power_rail):
        if power_rail.lx() < pin.lx():
            x_start, x_end = power_rail.lx(), pin.lx()
        else:
            x_start, x_end = pin.rx(), power_rail.rx()
        height = pin.height if isinstance(pin.height, float) else pin.height()
        self.add_rect(METAL1, vector(x_start, pin.by()),
                      width=x_end - x_start, height=height)
        offset = vector(power_rail.cx(), pin.cy())
        for via in [m1m2, m2m3, m3m4]:
            self.add_contact_center(via.layer_stack, offset, rotate=90,
                                    size=[1, 2])
        self.add_rect_center(METAL3, offset, width=self.m3_fill_width,
                             height=self.m3_fill_height)

    def add_poly_dummy(self):
        design.add_dummy_poly(self, self.mcc_insts[0].mod, self.mcc_insts, 1)
