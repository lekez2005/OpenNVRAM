import debug
from base import design
from base.contact import m1m2, m2m3
from base.vector import vector
from globals import OPTS
from modules.buffer_stage import BufferStage
from modules.logic_buffer import LogicBuffer
from pgates.pinv import pinv
from pgates.pnand2 import pnand2
from pgates.pnand3 import pnand3


class SwLogicBuffers(design.design):
    """
    Generate and buffer control signals using bank_sel, clk and search pins
    clk_buf is the clock buffer
    clk_bar is buffer of clk_bar
    sense_amp_en = cwrite_bar = AND(search, clk_bar)
    matchline_chb = NAND(search, clk)
    wordline_en = cwrite = AND3(bank_sel, search_bar, clk_bar)
    """
    name = "logic_buffers"

    nand = nand3 = inv = clk_buf = clk_bar = sense_amp_buf = wordline_buf = chb_buf = None
    clk_buf_inst = clk_bar_inst = clk_bar_internal_inst = search_bar_inst = wordline_internal_inst = None
    sense_amp_buf_inst = wordline_buf_inst = chb_buf_inst = None

    bank_sel_pin = clk_pin = search_pin = None

    rail_pos = [0.0] * 3

    def __init__(self, contact_nwell=True, contact_pwell=True):
        design.design.__init__(self, self.name)
        debug.info(2, "Create Logic Buffers gate")

        self.logic_heights = OPTS.logic_buffers_height

        self.contact_pwell = contact_pwell
        self.contact_nwell = contact_nwell

        self.create_layout()
        self.create_modules()

    def create_layout(self):
        self.add_pins()
        self.create_modules()
        self.calculate_rail_positions()
        self.add_modules()
        self.width = self.wordline_buf_inst.rx()
        self.add_input_pins()
        self.route_internal_signals()
        self.add_output_pins()
        self.add_power_pins()

    def create_modules(self):
        common_args = {
            'height': self.logic_heights,
            'contact_nwell': self.contact_nwell,
            'contact_pwell': self.contact_pwell,
        }
        buffer_args = common_args.copy()
        buffer_args.update(route_outputs=False)

        logic_args = buffer_args.copy()
        logic_args.update(route_inputs=False)

        self.nand = pnand2(**common_args)
        self.add_mod(self.nand)

        self.nand3 = pnand3(**common_args)
        self.add_mod(self.nand3)

        self.inv = pinv(**common_args)
        self.add_mod(self.inv)

        self.clk_buf = BufferStage(buffer_stages=OPTS.clk_buffers, **buffer_args)
        self.add_mod(self.clk_buf)

        self.clk_bar = BufferStage(buffer_stages=OPTS.clk_bar_buffers, **buffer_args)
        self.add_mod(self.clk_bar)

        assert len(OPTS.wordline_en_buffers) % 2 == 1, "Number of wordline buffers should be odd"
        self.wordline_buf = BufferStage(buffer_stages=OPTS.wordline_en_buffers, **buffer_args)
        self.add_mod(self.wordline_buf)

        assert len(OPTS.sense_amp_buffers) % 2 == 1, "Number of sense_amp buffers should be odd"
        self.sense_amp_buf = LogicBuffer(buffer_stages=OPTS.sense_amp_buffers, logic="pnand2", **logic_args)
        self.add_mod(self.sense_amp_buf)

        assert len(OPTS.chb_buffers) % 2 == 0, "Number of matchline buffers should be even"
        self.chb_buf = LogicBuffer(buffer_stages=OPTS.chb_buffers, logic="pnand2", **logic_args)
        self.add_mod(self.chb_buf)

    def calculate_rail_positions(self):
        self.rail_pos[0] = 0.0
        self.rail_pos[1] = self.m3_width + self.parallel_line_space
        self.rail_pos[2] = 2*(self.m3_width + self.parallel_line_space)

        self.height = self.rail_pos[2] + self.logic_heights

    def add_modules(self):

        y_offset = self.rail_pos[2] + self.m3_width - 0.5 * self.rail_height

        self.clk_buf_inst = self.add_inst("clk_buf", mod=self.clk_buf, offset=vector(0, y_offset))
        self.connect_inst(["clk", "clk_bar", "clk_buf", "vdd", "gnd"])

        self.chb_buf_inst = self.add_inst("chb", mod=self.chb_buf, offset=self.clk_buf_inst.lr())
        self.connect_inst(["clk", "search", "chb_buf", "ml_chb", "vdd", "gnd"])

        self.clk_bar_internal_inst = self.add_inst("clk_bar_internal", mod=self.inv, offset=self.chb_buf_inst.lr())
        self.connect_inst(["clk", "clk_bar_int", "vdd", "gnd"])

        self.sense_amp_buf_inst = self.add_inst("sense_amp", mod=self.sense_amp_buf,
                                                offset=self.clk_bar_internal_inst.lr())
        self.connect_inst(["search", "clk_bar_int", "sense_amp_en", "sense_amp_bar", "vdd", "gnd"])

        self.search_bar_inst = self.add_inst("search_bar_internal", mod=self.inv,
                                             offset=self.sense_amp_buf_inst.lr())
        self.connect_inst(["search", "search_bar", "vdd", "gnd"])

        self.wordline_internal_inst = self.add_inst("wl_internal", mod=self.nand3, offset=self.search_bar_inst.lr())
        self.connect_inst(["search_bar", "bank_sel", "clk_bar_int", "wl_int", "vdd", "gnd"])

        self.wordline_buf_inst = self.add_inst("wordline", mod=self.wordline_buf,
                                               offset=self.wordline_internal_inst.lr())
        self.connect_inst(["wl_int", "wordline_en", "wordline_bar", "vdd", "gnd"])

    def add_input_pins(self):
        self.bank_sel_pin = self.add_layout_pin("bank_sel", "metal3", offset=vector(0, self.rail_pos[2]),
                                                width=self.wordline_internal_inst.get_pin("B").cx())
        self.search_pin = self.add_layout_pin("search", "metal3", offset=vector(0, self.rail_pos[1]),
                                              width=self.search_bar_inst.get_pin("A").cx())
        self.clk_pin = self.add_layout_pin("clk", "metal3", offset=vector(0, self.rail_pos[0]),
                                           width=self.clk_bar_internal_inst.get_pin("A").lx())

    def route_internal_signals(self):
        # route_clk_buf
        self.route_from_rail_to_inverter(self.clk_pin, self.clk_buf_inst.get_pin("in"))

        # route  chb_buf
        self.route_rail_to_nand(self.clk_pin, self.chb_buf_inst.get_pin("A"), self.chb_buf_inst.get_pin("A").lx(),
                                via_dir="right")
        x_offset = self.chb_buf_inst.get_pin("A").lx() - self.line_end_space - self.m2_width
        self.route_rail_to_nand(self.search_pin, self.chb_buf_inst.get_pin("B"), x_offset, via_dir="left")

        # route clk_bar_int
        self.route_from_rail_to_inverter(self.clk_pin, self.clk_bar_internal_inst.get_pin("A"))
        # replace clk rail by clk_bar_int
        out_pin = self.clk_bar_internal_inst.get_pin("Z")
        dest_pin = self.wordline_internal_inst.get_pin("A")
        self.add_rect("metal3", offset=vector(out_pin.lx(), self.clk_pin.by()), width=dest_pin.rx()-out_pin.lx())
        self.add_rect("metal2", offset=vector(out_pin.lx(), self.clk_pin.by()), height=out_pin.by()-self.clk_pin.by())
        self.add_contact(m2m3.layer_stack, offset=vector(out_pin.cx()+0.5*m2m3.second_layer_height, self.clk_pin.by()),
                         rotate=90)

        # route sense amp
        self.route_rail_to_nand(self.search_pin, self.sense_amp_buf_inst.get_pin("A"),
                                self.sense_amp_buf_inst.get_pin("A").lx(), via_dir="right")
        x_offset = self.sense_amp_buf_inst.get_pin("A").lx() - self.line_end_space - self.m2_width
        self.route_rail_to_nand(self.clk_pin, self.sense_amp_buf_inst.get_pin("B"), x_offset, via_dir="right")

        # route search_bar
        self.route_from_rail_to_inverter(self.search_pin, self.search_bar_inst.get_pin("A"))

        # route wordline_internal_inst
        z_pin = self.search_bar_inst.get_pin("Z")
        a_pin = self.wordline_internal_inst.get_pin("A")
        self.add_rect("metal1", offset=z_pin.rc(), width=a_pin.lx()-z_pin.rx())

        self.route_rail_to_nand(self.bank_sel_pin, self.wordline_internal_inst.get_pin("B"),
                                self.wordline_internal_inst.get_pin("B").lx(), via_dir="right")
        x_offset = self.wordline_internal_inst.get_pin("B").lx() - self.line_end_space - self.m2_width
        self.route_rail_to_nand(self.clk_pin, self.wordline_internal_inst.get_pin("C"), x_offset, via_dir="left")

        # route wordline_buf_inst
        z_pin = self.wordline_internal_inst.get_pin("Z")
        in_pin = self.wordline_buf_inst.get_pin("in")
        self.add_rect("metal1", offset=vector(z_pin.rx(), in_pin.cy()-0.5*self.m1_width),
                      width=in_pin.lx() - z_pin.rx())

    def route_rail_to_nand(self, rail, pin, x_offset, via_dir="left"):
        self.add_contact_center(m1m2.layer_stack, offset=pin.center())
        self.add_rect("metal2", offset=vector(x_offset, pin.cy()-0.5*self.m2_width), width=pin.rx()-x_offset)
        self.add_rect("metal2", offset=vector(x_offset, rail.cy()), height=pin.cy()-rail.cy())
        if via_dir == "left":
            via_x = x_offset + self.m2_width
        else:
            via_x = x_offset+m2m3.second_layer_height
        self.add_contact(m2m3.layer_stack, offset=vector(via_x, rail.by()), rotate=90)

    def route_from_rail_to_inverter(self, rail, pin):
        x_offset = pin.lx() - self.m2_width
        self.add_contact_center(m1m2.layer_stack,
                                offset=vector(x_offset + 0.5 * m1m2.second_layer_height + self.m2_width,
                                              pin.cy()), rotate=90)
        y_offset = pin.cy() + 0.5 * m1m2.second_layer_width
        self.add_rect("metal2", offset=vector(x_offset, rail.cy()), height=y_offset - rail.cy())
        self.add_contact_center(m2m3.layer_stack, offset=vector(x_offset + 0.5 * self.m2_width, rail.cy()),
                                rotate=90)

    def add_output_pins(self):
        pin_names = ["ml_chb", "clk_buf", "clk_bar", "sense_amp_en", "wordline_en"]
        mod_names = ["out", "out", "out_inv", "out_inv", "out_inv"]
        instances = [self.chb_buf_inst, self.clk_buf_inst, self.clk_buf_inst, self.sense_amp_buf_inst,
                     self.wordline_buf_inst]
        for i in range(len(pin_names)):
            out_pin = instances[i].get_pin(mod_names[i])
            self.add_layout_pin(pin_names[i], "metal2", offset=out_pin.ul(), height=self.height-out_pin.uy())

    def add_power_pins(self):
        clk_buf_gnd = self.clk_buf_inst.get_pin("gnd")
        self.add_layout_pin("gnd", "metal1", offset=clk_buf_gnd.ll(), width=self.width-clk_buf_gnd.lx(),
                            height=clk_buf_gnd.height())
        clk_buf_vdd = self.clk_buf_inst.get_pin("vdd")
        self.add_layout_pin("vdd", "metal1", offset=clk_buf_vdd.ll(), width=self.width-clk_buf_vdd.lx(),
                            height=clk_buf_vdd.height())

    def add_pins(self):
        pins_str = "bank_sel clk search clk_buf clk_bar sense_amp_en wordline_en ml_chb vdd gnd"
        self.add_pin_list(pins_str.split(' '))
