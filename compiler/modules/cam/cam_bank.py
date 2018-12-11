from vector import vector
import cam_block
import contact
import copy
import debug
import design
from globals import OPTS
from math import log
import utils


class CamBank(design.design):
    """
    Generate a CAM bank
    """

    def __init__(self, word_size, num_words, words_per_row, name=""):

        if name == "":
            name = "bank_{0}_{1}".format(word_size, num_words)
        design.design.__init__(self, name)
        debug.info(2, "create cam bank of size {0} with {1} words".format(word_size, num_words))

        self.word_size = word_size
        self.num_words = num_words
        if words_per_row > 1:
            raise ValueError("Only 1 word per row is supported")
        self.words_per_row = words_per_row

        self.compute_sizes()

        self.block_insts = [None]*words_per_row
        self.create_layout()

        self.width = self.block_insts[-1].rx()
        self.height = self.block_insts[-1].uy()

    def compute_sizes(self):
        self.num_rows = self.num_words / self.words_per_row
        self.num_cols = self.words_per_row*self.word_size

        self.row_addr_size = int(log(self.num_rows, 2))
        self.col_addr_size = int(log(self.words_per_row, 2))
        self.addr_size = self.col_addr_size + self.row_addr_size

        debug.check(self.num_rows * self.num_cols == self.word_size * self.num_words, "Invalid bank sizes.")
        debug.check(self.addr_size == self.col_addr_size + self.row_addr_size, "Invalid address break down.")

        self.m2_pitch = contact.m2m3.width + self.parallel_line_space
        self.left_vdd_offset = 0

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("MASK[{0}]".format(i))
        for i in range(self.addr_size):
            self.add_pin("ADDR[{0}]".format(i))

        for pin in ["sel_all_banks", "bank_sel", "clk_buf", "s_en", "w_en", "search_en", "matchline_chb",
                    "mw_en", "sel_all_rows", "latch_tags", "vdd", "gnd"]:
            self.add_pin(pin)

    def create_layout(self):
        self.add_pins()
        self.create_modules()
        self.add_modules()
        self.calculate_rail_offsets()
        self.route_row_decoder()
        self.route_vdd_gnd()
        self.copy_block_properties()
        self.add_layout_pins()

    def copy_block_properties(self):
        """Copy properties defined in block and used in cam module"""
        self.bottom_power_layer = self.cam_block.bottom_power_layer
        self.top_power_layer = self.cam_block.top_power_layer


    def create_modules(self):

        self.cam_block = cam_block.CamBlock(self.word_size, self.num_rows, 1, 1, "cam_block")
        self.add_mod(self.cam_block)
        self.prefix = self.cam_block.prefix

        left_gnd = filter(lambda x: x.layer == "metal2",  self.cam_block.get_pins("gnd"))[0]
        self.cam_x_shift = left_gnd.lx() - self.cam_block.gnd_x_offset
        self.cam_y_shift = -self.cam_block.min_point

        self.row_decoder = self.cam_block.decoder

    def add_modules(self):
        predecoder_to_address_mux = self.row_decoder.predecoder_height - self.cam_block.address_mux_array_inst.offset[1]
        if self.row_decoder.height > self.cam_block.height:
            self.decoder_y_offset = 0
            self.cam_block_y_offset = predecoder_to_address_mux
        else:
            self.cam_block_y_offset = 0
            self.decoder_y_offset = -predecoder_to_address_mux
        self.add_row_decoder()
        self.add_cam_blocks()
        self.min_point = min(self.row_decoder_inst.by(), self.left_block.by())

    def add_cam_blocks(self):
        x_start = self.row_decoder_inst.lx() + self.row_decoder.row_decoder_width
        for col in range(self.words_per_row):
            x_offset = x_start + col * self.cam_block.width
            self.block_insts[col] = self.add_inst(name="cam_block{}".format(col), mod=self.cam_block,
                                                  offset=vector(x_offset, self.cam_block_y_offset))
            temp = []
            for i in range(self.word_size):
                temp.append("DATA[{0}]".format(i))
            for i in range(self.word_size):
                temp.append("MASK[{0}]".format(i))
            for i in range(self.num_rows):
                temp.append("dec_out[{0}]".format(i))

            temp.extend(["sel_all_banks", "bank_sel", "clk_buf", "s_en", "w_en", "search_en", "matchline_chb", "mw_en",
                         "sel_all_rows", "latch_tags", "block_gated_clk", "vdd", "gnd"])
            self.connect_inst(temp)
        self.left_block = self.block_insts[0]

    def add_row_decoder(self):
        right_vdd = max(filter(lambda x: x.layer == "metal1", self.cam_block.get_pins("vdd")), key=lambda x: x.rx())
        self.power_rail_width = right_vdd.width()
        x_offset = self.left_vdd_offset + self.power_rail_width + self.wide_m1_space
        self.row_decoder_inst = self.add_inst(name="row_decoder",
                                              mod=self.row_decoder,
                                              offset=vector(x_offset, self.decoder_y_offset))
        temp = []
        for i in range(self.row_addr_size):
            temp.append("ADDR[{0}]".format(i))
        for j in range(self.num_rows):
            temp.append("dec_out[{0}]".format(j))
        temp.extend(["block_gated_clk", "vdd", "gnd"])
        self.connect_inst(temp)

    def add_col_decoder(self):
        self.column_decoder_inst = self.add_inst("column_decoder", mod=self.column_decoder,
                                                 offset=vector(0, 0),
                                                 mirror="XY")
        temp = []
        temp.extend(["bank_sel", "sel_all_bar"])
        for i in range(self.addr_size):
            temp.append("ADDR[{0}]".format(i))
        for i in range(self.row_addr_size):
            temp.append("A[{0}]".format(i))
        if self.col_addr_size > 0:
            for i in range(2 ** self.col_addr_size):
                temp.append("sel[{}]".format(i))
        else:
            temp.append("vdd")
        temp.extend(["clk_buf", "vdd", "gnd"])
        self.connect_inst(temp)

    def calculate_rail_offsets(self):
        block_vdd_pins = self.left_block.get_pins("vdd")
        right_vdd = max(filter(lambda x: x.layer == "metal1", block_vdd_pins), key=lambda x: x.rx())
        self.power_rail_width = right_vdd.width()
        self.right_vdd_offset = right_vdd.lx()

        self.block_gnd = filter(lambda x: x.layer == "metal2", self.left_block.get_pins("gnd"))[0]




    def route_row_decoder(self):
        # decoder out to address mux in
        for row in range(self.cam_block.num_rows):
            decoder_out = self.row_decoder_inst.get_pin("decode[{}]".format(row))
            mux_in = self.cam_block.address_mux_array_inst.get_pin("dec[{}]".format(row))
            mux_in = utils.get_pin_rect(mux_in, [self.left_block])
            mux_cy = 0.5*(mux_in[0][1] + mux_in[1][1])
            self.add_path("metal1", [decoder_out.center(), vector(decoder_out.cx(), mux_cy),
                                     vector(mux_in[0][0], mux_cy)])

        # add address pins
        address_pin_space = contact.m2m3.second_layer_height + self.m3_width
        current_y = self.row_decoder_inst.get_pin("A[{}]".format(0)).by()
        y_index = 0
        for i in range(self.row_addr_size):
            pin_name = "A[{0}]".format(i)
            pin = self.row_decoder_inst.get_pin(pin_name)
            if not current_y == pin.by():
                current_y = pin.by()
                y_index = 0
            via_y = pin.by() + y_index * address_pin_space
            x_offset = self.row_decoder_inst.rx() + self.wide_m1_space + i * self.m2_pitch
            self.add_layout_pin("ADDR[{0}]".format(i), "metal2", offset=vector(x_offset, self.min_point),
                                height=max(via_y - self.min_point, self.metal1_minwidth_fill))
            self.add_rect("metal3", offset=vector(pin.lx(),
                                                  via_y + 0.5 * (contact.m2m3.second_layer_height - self.m2_width)),
                          width=x_offset - pin.lx())
            self.add_contact(contact.m2m3.layer_stack, offset=vector(pin.lx(), via_y))
            self.add_contact(contact.m2m3.layer_stack, offset=vector(x_offset, via_y))
            y_index += 1

        # connect clk
        block_clk = self.left_block.get_pin(self.prefix + "clk_buf")
        decoder_clks = self.row_decoder_inst.get_pins("clk")
        if len(decoder_clks) > 1:  # TODO fix clk order
            same_y = filter(lambda x: x.by() < block_clk.by() < x.uy(), decoder_clks)
            if len(same_y) > 0:
                decoder_clk = same_y[0]
            else:
                decoder_clk = decoder_clks[0]
        else:
            decoder_clk = decoder_clks[0]
        offset = vector(decoder_clk.lx(), block_clk.by())

        clk_rail_x = self.cam_block.rail_lines[self.prefix + "clk"]
        clk_rail_x = utils.transform_relative(vector(clk_rail_x + self.cam_x_shift, 0), self.left_block).x
        self.add_contact(contact.m2m3.layer_stack, offset=vector(clk_rail_x, block_clk.by()))

        self.add_rect("metal3", offset=offset, width=clk_rail_x - decoder_clk.lx())
        self.add_contact(contact.m2m3.layer_stack, offset=offset)

        if block_clk.uy() < decoder_clk.by():
            self.add_rect("metal2", offset=offset, height=decoder_clk.by() - offset.y)

        decoder_clk = min(decoder_clks, key=lambda x: x.by())

        # connect gnd pins
        highest_address_pin = self.row_decoder_inst.get_pin("A[{}]".format(self.addr_size-1))
        gnd_pins = filter(lambda x: x.uy() < highest_address_pin.uy() and x.by() > decoder_clk.by(),
                          self.row_decoder_inst.get_pins("gnd"))

        highest_pin = max(gnd_pins, key=lambda x: x.uy())
        lowest_pin = min(gnd_pins, key=lambda x: x.by())
        x_offset = lowest_pin.rx() + self.wide_m1_space
        sense_amp_gnd = utils.get_pin_rect(self.cam_block.sense_amp_array_inst.get_pins("gnd")[0], [self.left_block])
        self.add_rect("metal1", offset=vector(x_offset, lowest_pin.by()), height=highest_pin.uy() - lowest_pin.by(),
                      width=lowest_pin.height())
        self.add_rect("metal1", offset=vector(x_offset, sense_amp_gnd[0][1]),
                      height=sense_amp_gnd[1][1] - sense_amp_gnd[00][1], width=self.block_gnd.rx() - x_offset)

        for gnd_pin in gnd_pins:
            self.add_rect("metal1", offset=gnd_pin.lr(),
                          width=x_offset - gnd_pin.rx(), height=gnd_pin.height())

        # connect vdd pins
        for vdd_pin in self.row_decoder_inst.get_pins("vdd"):
            self.add_rect("metal1", offset=vector(self.left_vdd_offset, vdd_pin.by()),
                          width=vdd_pin.lx() - self.left_vdd_offset, height=vdd_pin.height())


    def route_vdd_gnd(self):
        # add left vdd
        self.add_layout_pin("vdd", "metal1", offset=vector(self.left_vdd_offset, self.min_point),
                            height=self.left_block.uy() - self.min_point,
                            width=self.power_rail_width)
        self.add_layout_pin("vdd", layer=self.cam_block.top_power_layer,
                            offset=vector(self.left_vdd_offset, self.min_point),
                            height=self.left_block.uy() - self.min_point, width=self.cam_block.grid_rail_width)

        self.vdd_grid_rects = []
        vdd_grid_insts = self.cam_block.vdd_via_insts
        vdd_via_y= map(lambda via_inst: utils.transform_relative(via_inst.offset, self.left_block).y, vdd_grid_insts)
        for via_y in vdd_via_y:
            self.vdd_grid_rects.append(self.add_inst(self.cam_block.m1mtop.name, self.cam_block.m1mtop,
                          offset=vector(self.left_vdd_offset, via_y)))
            self.connect_inst([])
            self.add_rect(self.cam_block.bottom_power_layer, offset=vector(self.left_vdd_offset, via_y),
                          height=self.cam_block.grid_rail_height,
                          width=self.right_vdd_offset-self.left_vdd_offset)

        # gnd rects
        self.gnd_grid_rects = copy.deepcopy(self.cam_block.gnd_grid_rects)
        for rect in self.gnd_grid_rects:
            rect.offset = rect.offset + self.left_block.ll()




    def add_layout_pins(self):

        # copy pins
        self.copy_layout_pin(self.left_block, "vdd", "vdd")
        self.copy_layout_pin(self.left_block, "gnd", "gnd")
        self.copy_layout_pin(self.left_block, "block_sel", "bank_sel")
        self.copy_layout_pin(self.left_block, "sel_all_banks", "sel_all_banks")
        self.copy_layout_pin(self.left_block, "clk_buf", "clk_buf")
        self.copy_layout_pin(self.left_block, "s_en", "s_en")
        self.copy_layout_pin(self.left_block, "w_en", "w_en")
        self.copy_layout_pin(self.left_block, "search_en", "search_en")
        self.copy_layout_pin(self.left_block, "matchline_chb", "matchline_chb")
        self.copy_layout_pin(self.left_block, "mw_en", "mw_en")
        self.copy_layout_pin(self.left_block, "sel_all_rows", "sel_all_rows")
        self.copy_layout_pin(self.left_block, "latch_tags", "latch_tags")
        for i in range(self.word_size):
            for name_template in ["MASK[{}]", "DATA[{}]"]:
                pin_name = name_template.format(i)
                self.copy_layout_pin(self.left_block, pin_name, pin_name)



