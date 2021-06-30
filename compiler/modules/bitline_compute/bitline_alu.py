from base import utils
from base.contact import m1m2, m2m3, m3m4, contact
from base.design import design
from base.library_import import library_import
from base.vector import vector
from globals import OPTS
from modules.internal_decoder_bank import InternalDecoderBank
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

    def __init__(self, bank, num_cols, word_size, cells_per_group, inverter_size=1):
        super().__init__("alu_{}".format(num_cols))
        self.num_cols = num_cols
        self.inverter_size = inverter_size
        self.word_size = word_size
        self.num_words = int(num_cols/word_size)
        self.bank = bank  # type: InternalDecoderBank

        assert word_size % cells_per_group == 0, "Number of cells per group should be a factor of word size to even out"

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

        for word in range(self.num_words):
            self.add_pin_list(["cin[{}]".format(word), "cout[{}]".format(word)])

        self.add_pin_list(["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor", "s_sum", "s_data_in",  # select data
                           "s_mask_in", "s_bus", "s_shift", "s_sr", "s_lsb", "s_msb"])  # mask select
        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            self.add_pin_list(["sr_en", "latch_clk", "sr_clk", "vdd", "gnd"])
        else:
            self.add_pin_list(["sr_en", "sr_clk", "vdd", "gnd"])

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

        if OPTS.run_optimizations:
            delay_strategy = delay_strategy_class()(self.bank)
            sizes = delay_strategy.get_alu_clk_sizes()
        else:
            sizes = OPTS.sr_clk_buffers
        self.clk_buf = LogicBuffer(buffer_stages=sizes, logic="pnand2", height=OPTS.logic_buffers_height,
                                   contact_nwell=True, contact_pwell=True)

        self.add_mod(self.clk_buf)

    def route_layout(self):

        # get grid locations
        grid_pitch = self.m4_width + self.parallel_line_space
        self.m4_grid = [0.5 * self.m4_width + x * grid_pitch for x in range(6)]

        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            self.route_latch_clk()

        self.copy_layout_pins()

        self.route_msb_lsb()
        self.route_shift_ins()
        self.route_carries()
        self.route_vdd_gnd()
        self.route_sr_clk()
        self.add_poly_dummy()

    def add_modules(self):

        self.bank_x_shift = self.bank.bitcell_array_inst.lx()

        and_pin = self.bank.get_pin("and[0]")
        self.bank_y_shift = self.mcc_col.height - and_pin.by()

        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.num_cols)

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
                                     offset=vector(self.bitcell_offsets[col]+self.bank_x_shift, current_cell.height),
                                     mirror="MX")
            self.mcc_insts.append(mcc_inst)

            shift_in = "shift_out[{}]".format(col + 1)
            shift_out = "shift_out[{}]".format(col)

            msb_in = "shift_out[{}]".format((current_word + 1) * self.word_size - 1)
            lsb_in = "shift_out[{}]".format(current_word * self.word_size)

            cin = cin_template.format(col-1)
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

        for x_offset in self.tap_offsets:
            self.add_inst(self.col_tap.name, self.col_tap, vector(x_offset+self.bank_x_shift, self.col_tap.height),
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

        decoder_y = self.bank.row_decoder_inst.offset.y + self.bank_y_shift

        y_offset = min(closest_vdd.cy() + self.clk_buf.height,
                       decoder_y - self.implant_space - self.rail_height - self.wide_m1_space)

        x_offset = self.bank.mid_vdd.lx() - self.wide_m1_space - self.clk_buf.width

        self.clk_buf_inst = self.add_inst("clk_buf", mod=self.clk_buf,
                                          offset=vector(x_offset, y_offset), mirror="MX")

        self.connect_inst(self.get_clk_buf_connections())

    def route_latch_clk(self):
        bank_clk_pin = self.bank.get_pin("clk_buf")
        latch_clk_pins = self.mcc_insts[0].get_pins("latch_clk")

        top_clk_pin = max(latch_clk_pins, key=lambda x: x.uy())
        bot_clk_pin = min(latch_clk_pins, key=lambda x: x.by())

        instances_x_diff = [x.lx() - bank_clk_pin.lx() for x in self.mcc_insts]

        valid_pins = list(filter(lambda x: x > 0, instances_x_diff))
        if len(valid_pins) > 0:
            closest_x = min(valid_pins) + bank_clk_pin.lx()
        else:
            closest_x = bank_clk_pin.lx()
            self.add_rect("metal1", offset=top_clk_pin.lr(), width=closest_x-top_clk_pin.rx())
            self.add_rect("metal1", offset=bot_clk_pin.lr(), width=self.m4_grid[4] + closest_x-bot_clk_pin.rx())

        bank_pin_y = bank_clk_pin.by() + self.bank_y_shift

        bend_y = self.mcc_insts[0].uy() + self.line_end_space
        self.add_rect("metal2", offset=vector(bank_clk_pin.lx(), bend_y),
                      height=bank_pin_y-bend_y)

        self.add_contact(m1m2.layer_stack, offset=vector(bank_clk_pin.lx(),
                                                         bend_y+0.5*(self.m3_width-m1m2.height)))
        self.add_rect("metal1", offset=vector(bank_clk_pin.lx(), top_clk_pin.by()), height=bend_y-top_clk_pin.by())

        rail_x = closest_x + self.m4_grid[4]

        self.add_contact(m2m3.layer_stack, offset=vector(bank_clk_pin.lx()+m2m3.height, bend_y), rotate=90)
        self.add_rect("metal3", offset=vector(bank_clk_pin.lx(), bend_y), width=rail_x-bank_clk_pin.lx())
        self.add_contact(m3m4.layer_stack, offset=vector(rail_x, bend_y+self.m3_width-m3m4.height))
        self.add_rect("metal4", offset=vector(rail_x, bot_clk_pin.by()), height=bend_y-bot_clk_pin.by())

        offset = vector(rail_x+0.5*self.m4_width, bot_clk_pin.cy())
        self.add_contact_center(m1m2.layer_stack, offset=offset, rotate=90)
        self.add_contact_center(m2m3.layer_stack, offset=offset)
        self.add_contact_center(m3m4.layer_stack, offset=offset)

        fill_width = utils.ceil(drc["minarea_metal3_drc"]/m3m4.height)
        x_offset = offset.x - 0.5*fill_width
        y_offset = offset.y - 0.5*m3m4.height
        self.add_rect("metal2", offset=vector(x_offset, y_offset), width=fill_width, height=m3m4.height)
        self.add_rect("metal3", offset=vector(x_offset, y_offset), width=fill_width, height=m3m4.height)

        self.add_layout_pin("latch_clk", top_clk_pin.layer, offset=top_clk_pin.ll(),
                            width=self.mcc_insts[-1].get_pins("latch_clk")[0].rx()-top_clk_pin.lx())

    def copy_layout_pins(self):
        source_names = ("s_and s_data_in s_nand s_nor s_or s_xnor s_xor "
                        "s_add s_mask_in s_bus s_shft s_sr s_lsb s_msb ").split()

        for pin_name in source_names:
            pin = self.mcc_insts[0].get_pin(pin_name)
            dest_pin = pin_name
            if pin_name == "s_shft":
                dest_pin = "s_shift"
            self.add_layout_pin(dest_pin, pin.layer, offset=pin.ll(), height=pin.height(),
                                width=self.mcc_insts[-1].get_pin(pin_name).rx()-pin.lx())

        for i in range(self.num_words):
            col = i*self.word_size
            self.copy_layout_pin(self.mcc_insts[col], "cin", "cin[{}]".format(i))

        for i in range(self.num_words):
            col = (i+1)*self.word_size-1
            self.copy_layout_pin(self.mcc_insts[col], "cout", "cout[{}]".format(i))

        for col in range(self.num_cols):
            self.copy_layout_pin(self.mcc_insts[col], "out", "bus_out[{}]".format(col))
            self.copy_layout_pin(self.mcc_insts[col], "mask_bar_out", "mask_bar_out[{}]".format(col))
            self.copy_layout_pin(self.mcc_insts[col], "data_in", "data_in[{}]".format(col))
            self.copy_layout_pin(self.mcc_insts[col], "mask_in", "mask_in[{}]".format(col))

        self.copy_layout_pin(self.clk_buf_inst, "A", "sr_en")

    def route_msb_lsb(self):
        for i in range(self.num_words):
            col = i*self.word_size
            msb_index = col + self.word_size - 1
            for pin_name in ["msb", "lsb"]:
                first_pin = self.mcc_insts[col].get_pin(pin_name)
                last_pin = self.mcc_insts[msb_index].get_pin(pin_name)
                self.add_rect(first_pin.layer, offset=first_pin.ll(), width=last_pin.rx()-first_pin.lx(),
                              height=first_pin.height())

                # connect
                if pin_name == "lsb":
                    source_pins = self.mcc_insts[col].get_pins("shift_out")
                else:
                    source_pins = self.mcc_insts[msb_index].get_pins("shift_out")
                source_pin = list(filter(lambda x: x.layer == "metal4", source_pins))[0]

                self.add_contact(m3m4.layer_stack, offset=vector(source_pin.rx(), first_pin.by()), rotate=90)

    def route_shift_ins(self):
        for word in range(self.num_words):
            for i in range(self.word_size-1):
                col = word*self.word_size + i
                next_col = col + 1

                shift_out = list(filter(lambda x: x.layer == "metal3",
                                        self.mcc_insts[next_col].get_pins("shift_out")))[0]
                shift_in = self.mcc_insts[col].get_pin("shift_in")

                self.add_rect("metal3", offset=vector(shift_in.rx(), shift_out.by()),
                              width=shift_out.lx()-shift_in.rx(), height=shift_out.height())

            # msb shift in to gnd
            gnd_pins = self.mcc_insts[0].get_pins("gnd")
            col = word*self.word_size + self.word_size - 1
            shift_in = self.mcc_insts[col].get_pin("shift_in")

            closest_gnd = min(filter(lambda x: x.by() < shift_in.by(), gnd_pins),
                              key=lambda x: shift_in.by()-x.by())
            self.add_rect("metal3", offset=vector(shift_in.rx()-self.m3_width, closest_gnd.cy()),
                          height=shift_in.by()-closest_gnd.cy())

            fill_width = utils.ceil(drc["minarea_metal3_drc"] / m2m3.height)
            x_offset = shift_in.rx()-0.5*(self.m3_width + fill_width)
            y_offset = closest_gnd.cy() - 0.5*m2m3.height
            self.add_rect("metal2", offset=vector(x_offset, y_offset), width=fill_width, height=m2m3.height)
            self.add_contact_center(m2m3.layer_stack, offset=vector(shift_in.rx() - 0.5*self.m2_width,
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
                        prev_cout = self.mcc_insts[col-1].get_pin("coutb")
                        cin = self.mcc_insts[col].get_pin("cinb")
                    self.add_rect(cin.layer, offset=prev_cout.lr(), width=cin.lx() - prev_cout.rx())

    def route_sr_clk(self):

        # clk pin
        clk_pin = self.mcc_insts[0].get_pin("clk")
        out_pin = self.clk_buf_inst.get_pin("out_inv")
        self.add_rect("metal1", offset=vector(out_pin.lx(), clk_pin.by()), width=clk_pin.lx()-out_pin.lx(),
                      height=clk_pin.height())

        buffer_center_y = 0.5*(self.clk_buf_inst.uy() + self.clk_buf_inst.by())
        self.add_rect("metal1", offset=vector(out_pin.lx(), buffer_center_y), width=out_pin.width(),
                      height=clk_pin.cy()-buffer_center_y)

        # connect vdd
        vdd_pins = self.mcc_insts[0].get_pins("vdd")
        closest_vdd = min(filter(lambda x: x.uy() < clk_pin.by(), vdd_pins), key=lambda x: clk_pin.by()-x.by())

        buf_vdd = self.clk_buf_inst.get_pin("vdd")
        x_offset = buf_vdd.rx() + self.line_end_space

        self.add_rect("metal1", offset=vector(x_offset, buf_vdd.by()), width=buf_vdd.height(),
                      height=closest_vdd.uy() - buf_vdd.by())
        self.add_rect("metal1", offset=vector(x_offset, closest_vdd.by()),
                      width=closest_vdd.lx() - x_offset, height=closest_vdd.height())
        self.add_rect("metal1", offset=buf_vdd.lr(), width=x_offset - buf_vdd.rx(), height=buf_vdd.height())

        closest_gnd = min(filter(lambda x: x.by() > clk_pin.by(), self.mcc_insts[0].get_pins("gnd")),
                          key=lambda x: x.by() - clk_pin.by())

        buf_gnd = self.clk_buf_inst.get_pin("gnd")
        self.add_rect("metal1", offset=buf_gnd.lr(), width=buf_gnd.height(), height=closest_gnd.uy()-buf_gnd.by())
        self.add_rect("metal1", offset=vector(buf_gnd.rx(), closest_gnd.by()),
                      width=closest_gnd.lx()-buf_gnd.rx(), height=closest_gnd.height())

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

    def route_vdd_gnd(self):

        layout_names = ["vdd", "gnd", "vdd", "gnd"]
        rail_names = ["mid_vdd", "mid_gnd", "right_vdd", "right_gnd"]
        for i in range(4):
            rail = getattr(self.bank, rail_names[i])

            pin = self.add_layout_pin(layout_names[i], rail.layer, offset=vector(rail.lx(), 0),
                                      width=rail.width(), height=self.height)
            setattr(self, rail_names[i], pin)

        right_x = self.mcc_insts[-1].rx()

        for pin in self.mcc_insts[0].get_pins("vdd"):
            self.add_power_via(pin, self.mid_vdd)
            self.add_power_via(pin, self.right_vdd)

            self.add_rect("metal1", offset=vector(self.mid_vdd.cx(), pin.by()),
                          width=pin.lx()-self.mid_vdd.cx(), height=pin.height())

            self.add_rect("metal1", offset=vector(right_x, pin.by()), width=self.right_vdd.cx()-right_x,
                          height=pin.height())

        left_gnds = list(sorted(self.mcc_insts[0].get_pins("gnd"), key=lambda x: x.cy()))
        right_gnds = list(sorted(self.mcc_insts[-1].get_pins("gnd"), key=lambda x: x.cy()))
        for i in range(len(left_gnds)):
            pin = left_gnds[i]
            self.add_power_via(pin, self.mid_gnd)

            self.add_rect("metal1", offset=vector(self.mid_gnd.cx(), pin.by()),
                          width=pin.lx() - self.mid_gnd.cx(), height=pin.height())

            self.add_rect("metal1", offset=vector(right_x, right_gnds[i].by()),
                          width=self.right_gnd.cx() - right_gnds[i].rx(), height=right_gnds[i].height())

        grid_space = drc["power_grid_space"]

        grid_rail_height = self.bank.grid_rail_height

        def filter_grid(x):
            # TODO make this non-arbitrary
            return list(filter(lambda x: x < self.height - 8, x))

        grid_pitch = grid_space + grid_rail_height

        gnd_horz = filter_grid([x * 2 * grid_pitch for x in range(5)])
        vdd_horz = filter_grid([x * 2 * grid_pitch + grid_pitch for x in range(5)])

        for y in gnd_horz + vdd_horz:
            self.add_rect(self.bank.bottom_power_layer, offset=vector(self.mid_gnd.lx(), y),
                          width=self.right_gnd.rx()-self.mid_gnd.lx(), height=grid_rail_height)

        for i in range(len(self.bank.vertical_power_rails_pos)):
            x_offset = self.bank.vertical_power_rails_pos[i] + self.bank_x_shift
            self.add_rect(self.bank.top_power_layer, offset=vector(x_offset, 0),
                          width=self.bank.grid_rail_width, height=self.height)

            if i % 2 == 0:
                for y in vdd_horz:

                    self.add_inst(self.bank.m9m10.name, mod=self.bank.m9m10,
                                  offset=vector(x_offset, y))
                    self.connect_inst([])
            else:
                for y in gnd_horz:
                    self.add_inst(self.bank.m9m10.name, mod=self.bank.m9m10,
                                  offset=vector(x_offset, y))
                    self.connect_inst([])

        rails = utils.get_libcell_pins(["vdd", "gnd"], OPTS.body_tap)
        vdd_rail = rails["vdd"][0]
        gnd_rail = rails["gnd"][0]

        height = self.height + 5

        dummy_contact = contact(layer_stack=("metal4", "via4", "metal5"), dimensions=[1, 5])

        for x_offset in self.tap_offsets:
            vdd_x = vdd_rail.lx() + x_offset + self.bank_x_shift
            self.add_rect("metal4", offset=vector(vdd_x, 0), height=height, width=vdd_rail.width())

            for y in vdd_horz:
                self.add_contact(layers=dummy_contact.layer_stack, size=dummy_contact.dimensions,
                                 offset=vector(vdd_x, y))
                self.add_inst(self.bank.m5m9.name, mod=self.bank.m5m9, offset=vector(vdd_x, y))
                self.connect_inst([])

            gnd_x = gnd_rail.lx() + x_offset + self.bank_x_shift
            self.add_rect("metal4", offset=vector(gnd_x, 0), height=height, width=gnd_rail.width())

            for y in gnd_horz:
                self.add_contact(layers=dummy_contact.layer_stack, size=dummy_contact.dimensions,
                                 offset=vector(gnd_x, y))
                self.add_inst(self.bank.m5m9.name, mod=self.bank.m5m9, offset=vector(gnd_x, y))
                self.connect_inst([])

        # connect taps vdd

    def add_power_via(self, pin, power_pin, via_rotate=90):
        self.add_contact_center(m1m2.layer_stack, offset=vector(power_pin.cx(), pin.cy()),
                                size=[2, 1], rotate=via_rotate)

    def add_poly_dummy(self):
        x_offset = self.mcc_insts[-1].rx() + self.poly_pitch - 0.5*self.poly_width
        self.add_rect("po_dummy", offset=vector(x_offset, 0), height=self.mcc_insts[-1].height,
                      width=self.poly_width)
