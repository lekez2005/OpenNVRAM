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


class LogicBuffers(design.design):
    """
    Generate and buffer control signals using bank_sel, clk and search pins
    clk_buf is the clock buffer
    internal signal write = NAND(bank_sel, search)
    internal signal search_int = NOT(write)
    write_buf is write buffer
    sense_amp_en = clk_bar.search_int = NOR(clk, write)
    wordline_en = clk_bar.write = NOR(clk, search_int)
    ml_chb = NOT(clk.search) = NAND(clk, search_int)
    """
    name = "logic_buffers"

    nand = nand3 = inv = inv2 = clk_buf = write_buf = sense_amp_buf = wordline_buf = chb_buf = None
    clk_buf_inst = clk_bar_internal_inst = write_bar_int_inst = write_bar_inst = search_bar_inst = None
    sense_amp_buf_inst = wordline_buf_inst = chb_buf_inst = None

    bank_sel_pin = clk_pin = search_pin = None

    rail_pos = [0.0]*4

    def __init__(self, contact_nwell=True, contact_pwell=True):
        design.design.__init__(self, self.name)
        debug.info(2, "Create Logic Buffers gate")

        self.logic_heights = OPTS.logic_buffers_height
        self.contact_pwell = contact_pwell
        self.contact_nwell = contact_nwell

        self.create_layout()

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

        self.inv2 = pinv(size=2, **common_args)
        self.add_mod(self.inv2)

        self.clk_buf = BufferStage(buffer_stages=OPTS.clk_buffers, **buffer_args)
        self.add_mod(self.clk_buf)

        assert len(OPTS.write_buffers) % 2 == 0, "Number of write buffers should be odd"
        self.write_buf = BufferStage(buffer_stages=OPTS.write_buffers, **buffer_args)
        self.add_mod(self.write_buf)

        assert len(OPTS.wordline_en_buffers) % 2 == 0, "Number of wordline buffers should be even"
        self.wordline_buf = LogicBuffer(buffer_stages=OPTS.wordline_en_buffers, logic="pnor2", **logic_args)
        self.add_mod(self.wordline_buf)

        assert len(OPTS.sense_amp_buffers) % 2 == 1, "Number of sense_amp buffers should be odd"
        self.sense_amp_buf = LogicBuffer(buffer_stages=OPTS.sense_amp_buffers, logic="pnand2", **logic_args)
        self.add_mod(self.sense_amp_buf)

        assert len(OPTS.chb_buffers) % 2 == 0, "Number of matchline buffers should be even"
        self.chb_buf = LogicBuffer(buffer_stages=OPTS.chb_buffers, logic="pnand2", **logic_args)
        self.add_mod(self.chb_buf)
        self.add_mod(self.chb_buf)

    def add_modules(self):
        y_offset = self.rail_pos[2] + self.m3_width - 0.5*self.rail_height

        self.search_bar_inst = self.add_inst("search_bar_internal", mod=self.inv,
                                             offset=vector(0, y_offset))
        self.connect_inst(["search", "search_bar", "vdd", "gnd"])

        self.write_bar_int_inst = self.add_inst("write_bar_internal", mod=self.nand, offset=self.search_bar_inst.lr())
        self.connect_inst(["search_bar", "bank_sel", "write_bar_internal", "vdd", "gnd"])

        self.chb_buf_inst = self.add_inst("chb", mod=self.chb_buf, offset=self.write_bar_int_inst.lr())
        self.connect_inst(["search", "clk", "chb_buf", "ml_chb", "vdd", "gnd"])

        self.clk_buf_inst = self.add_inst("clk_buf", mod=self.clk_buf, offset=self.chb_buf_inst.lr())
        self.connect_inst(["clk", "clk_buf_bar", "clk_buf", "vdd", "gnd"])

        # Caution: clk_bar is not buffered
        self.clk_bar_internal_inst = self.add_inst("clk_bar_internal", mod=self.inv2, offset=self.clk_buf_inst.lr())
        self.connect_inst(["clk", "clk_bar", "vdd", "gnd"])

        self.sense_amp_buf_inst = self.add_inst("sense_amp", mod=self.sense_amp_buf,
                                                offset=self.clk_bar_internal_inst.lr())
        self.connect_inst(["clk_bar", "search", "sense_amp_en", "search_cbar", "vdd", "gnd"])

        self.write_bar_inst = self.add_inst("write_bar", mod=self.write_buf, offset=self.sense_amp_buf_inst.lr())
        self.connect_inst(["write_bar_internal", "write_buf", "write_bar", "vdd", "gnd"])

        self.wordline_buf_inst = self.add_inst("wordline", mod=self.wordline_buf, offset=self.write_bar_inst.lr())
        self.connect_inst(["write_bar", "clk_bar", "wordline_bar", "wordline_en", "vdd", "gnd"])

    def calculate_rail_positions(self):
        self.rail_pos[0] = 0.0
        self.rail_pos[1] = self.m3_width + self.parallel_line_space
        self.rail_pos[2] = 2*(self.m3_width + self.parallel_line_space)

        self.height = self.rail_pos[2] + self.logic_heights

    def add_input_pins(self):
        self.bank_sel_pin = self.add_layout_pin("bank_sel", "metal3", offset=vector(0, self.rail_pos[2]),
                                                width=self.write_bar_int_inst.get_pin("B").cx())
        self.search_pin = self.add_layout_pin("search", "metal3", offset=vector(0, self.rail_pos[1]),
                                              width=self.sense_amp_buf_inst.get_pin("B").cx())
        self.clk_pin = self.add_layout_pin("clk", "metal3", offset=vector(0, self.rail_pos[0]),
                                           width=self.clk_bar_internal_inst.get_pin("A").lx())

    def route_internal_signals(self):
        # route search_bar
        a_pin = self.search_bar_inst.get_pin("A")
        self.add_contact_center(m1m2.layer_stack, a_pin.center(), rotate=90)
        x_offset = a_pin.cx() - 0.5*m1m2.second_layer_height - self.m2_width
        self.add_rect("metal2", offset=vector(x_offset, self.search_pin.by()),
                      height=a_pin.cy()+0.5*m1m2.second_layer_width-self.search_pin.by())
        self.add_contact_center(m2m3.layer_stack, offset=vector(x_offset+0.5*self.m2_width, self.search_pin.cy()),
                                rotate=90)
        # search_bar pin to write_int
        z_pin = self.search_bar_inst.get_pin("Z")
        a_pin = self.write_bar_int_inst.get_pin("A")
        self.add_rect("metal1", offset=vector(z_pin.rx(), z_pin.cy()-0.5*self.m1_width),
                      width=a_pin.lx()-z_pin.rx())

        # bank_sel to write_int B pin
        b_pin = self.write_bar_int_inst.get_pin("B")
        self.add_contact_center(m1m2.layer_stack, b_pin.center())
        x_offset = b_pin.lx() - self.m2_width - 0.5*self.m2_space
        self.add_rect("metal2", offset=vector(x_offset, self.bank_sel_pin.cy()),
                      height=b_pin.cy()-0.5*m1m2.second_layer_height+self.m2_width - self.bank_sel_pin.cy())
        self.add_rect("metal2", offset=vector(x_offset, b_pin.cy()-0.5*m1m2.second_layer_height),
                      width=b_pin.lx()-x_offset)
        self.add_contact_center(m2m3.layer_stack, offset=vector(x_offset+0.5*self.m2_width, self.bank_sel_pin.cy()),
                                rotate=90)

        # chb
        a_pin = self.chb_buf_inst.get_pin("A")
        self.add_rect("metal2", offset=vector(a_pin.lx(), self.search_pin.cy()), height=a_pin.cy()-self.search_pin.cy())
        self.add_contact_center(m1m2.layer_stack, offset=a_pin.center())
        self.add_contact_center(m2m3.layer_stack, offset=vector(a_pin.cx(), self.search_pin.cy()), rotate=90)

        b_pin = self.chb_buf_inst.get_pin("B")
        b_pin_inverter = self.chb_buf.get_pin("B")
        x_offset = b_pin.cx() + self.chb_buf.logic_mod.width - b_pin_inverter.cx() + self.m2_space
        self.add_contact_center(m1m2.layer_stack, offset=b_pin.center())
        y_offset = b_pin.cy()-0.5*m1m2.second_layer_height
        self.add_rect("metal2", offset=vector(b_pin.rx(), y_offset), width=x_offset + self.m2_width-b_pin.rx())
        self.add_rect("metal2", offset=vector(x_offset, self.clk_pin.cy()), height=y_offset-self.clk_pin.cy())
        self.add_contact_center(m2m3.layer_stack, offset=vector(x_offset+0.5*self.m2_width, self.clk_pin.cy()),
                                rotate=90)

        # clk_buf
        in_pin = self.clk_buf_inst.get_pin("in")
        x_offset = in_pin.lx()-self.m2_width
        self.add_contact_center(m1m2.layer_stack, offset=vector(x_offset+0.5*m1m2.second_layer_height+self.m2_width,
                                                                in_pin.cy()), rotate=90)
        y_offset = in_pin.cy() + 0.5*m1m2.second_layer_width
        self.add_rect("metal2", offset=vector(x_offset, self.clk_pin.cy()), height=y_offset-self.clk_pin.cy())
        self.add_contact_center(m2m3.layer_stack, offset=vector(x_offset+0.5*self.m2_width, self.clk_pin.cy()),
                                rotate=90)

        # clk_bar_int
        a_pin = self.clk_bar_internal_inst.get_pin("A")
        x_offset = a_pin.lx() - self.m2_width
        self.add_contact_center(m1m2.layer_stack,
                                offset=vector(x_offset + 0.5 * m1m2.second_layer_height + self.m2_width,
                                              a_pin.cy()), rotate=90)
        y_offset = a_pin.cy() + 0.5 * m1m2.second_layer_width
        self.add_rect("metal2", offset=vector(x_offset, self.clk_pin.cy()), height=y_offset - self.clk_pin.cy())
        self.add_contact_center(m2m3.layer_stack, offset=vector(x_offset + 0.5 * self.m2_width, self.clk_pin.cy()),
                                rotate=90)
        # rail to write_bar
        z_pin = self.clk_bar_internal_inst.get_pin("Z")
        clk_bar_int_rect = self.add_rect("metal3", offset=vector(z_pin.lx(), self.clk_pin.by()),
                                         width=self.wordline_buf_inst.get_pin("A").lx()-z_pin.lx())
        self.add_rect("metal2", offset=vector(z_pin.lx(), self.clk_pin.cy()), height=z_pin.by()-self.clk_pin.cy())
        self.add_contact_center(m2m3.layer_stack, offset=vector(z_pin.cx(), self.clk_pin.cy()), rotate=90)

        # clk_bar to sense_amp A pin
        a_pin = self.sense_amp_buf_inst.get_pin("A")
        self.add_rect("metal1", offset=z_pin.rc(), width=a_pin.lx()-z_pin.rx())
        # search pin to B pin
        b_pin = self.sense_amp_buf_inst.get_pin("B")
        x_offset = b_pin.lx()-self.m2_width
        y_offset = b_pin.cy() + 0.5*m1m2.second_layer_height
        self.add_contact_center(m1m2.layer_stack, offset=b_pin.center())
        self.add_rect("metal2", offset=vector(x_offset, self.search_pin.cy()), height=y_offset-self.search_pin.cy())
        self.add_contact_center(m2m3.layer_stack, offset=vector(x_offset+0.5*self.m2_width, self.search_pin.cy()),
                                rotate=90)

        # write_bar
        write_int_z = self.write_bar_int_inst.get_pin("Z")
        in_pin = self.write_bar_inst.get_pin("in")
        y_offset = self.bank_sel_pin.by()
        self.add_rect("metal2", offset=vector(write_int_z.lx(), y_offset), height=write_int_z.by()-y_offset)
        self.add_contact_center(m2m3.layer_stack, offset=vector(write_int_z.cx(), y_offset+0.5*self.m2_width),
                                rotate=90)
        self.add_rect("metal3", offset=vector(write_int_z.lx(), y_offset), width=in_pin.lx()-write_int_z.lx())

        x_offset = in_pin.lx()-self.m2_width
        self.add_contact_center(m2m3.layer_stack, offset=vector(x_offset+0.5*self.m2_width, self.bank_sel_pin.cy()),
                                rotate=90)
        self.add_rect("metal2", offset=vector(x_offset, y_offset),
                      height=in_pin.cy()+0.5*m1m2.second_layer_width-y_offset)
        self.add_contact_center(m1m2.layer_stack, offset=vector(in_pin.lx()+0.5*m1m2.second_layer_height, in_pin.cy()),
                                rotate=90)

        # wordline
        out_pin = self.write_bar_inst.get_pin("out")
        a_pin = self.wordline_buf_inst.get_pin("A")
        self.add_rect("metal1", offset=vector(out_pin.rx(), a_pin.cy()), width=a_pin.lx()-out_pin.rx())

        b_pin = self.wordline_buf_inst.get_pin("B")
        x_offset = a_pin.lx() - self.m2_width - self.m2_space
        self.add_rect("metal2", offset=vector(x_offset, clk_bar_int_rect.by()),
                      height=b_pin.by()-clk_bar_int_rect.by())
        self.add_rect("metal2", offset=vector(x_offset, b_pin.by()), width=b_pin.cx()-x_offset)
        self.add_contact_center(m1m2.layer_stack, b_pin.center())
        self.add_contact_center(m2m3.layer_stack, offset=vector(x_offset+0.5*self.m2_width,
                                                                clk_bar_int_rect.by()+0.5*self.m2_width),
                                rotate=90)

    def add_output_pins(self):
        pin_names = ["ml_chb", "clk_buf", "sense_amp_en", "search_cbar", "write_bar", "wordline_en"]
        mod_names = ["out", "out", "out_inv", "out", "out", "out"]
        instances = [self.chb_buf_inst, self.clk_buf_inst, self.sense_amp_buf_inst, self.sense_amp_buf_inst,
                     self.write_bar_inst, self.wordline_buf_inst]
        for i in range(len(pin_names)):
            out_pin = instances[i].get_pin(mod_names[i])
            self.add_layout_pin(pin_names[i], "metal2", offset=out_pin.ul(), height=self.height-out_pin.uy())

    def add_power_pins(self):
        search_bar_gnd = self.search_bar_inst.get_pin("gnd")
        self.add_layout_pin("gnd", "metal1", offset=search_bar_gnd.ll(), width=self.width-search_bar_gnd.lx(),
                            height=search_bar_gnd.height())
        search_bar_vdd = self.search_bar_inst.get_pin("vdd")
        self.add_layout_pin("vdd", "metal1", offset=search_bar_vdd.ll(), width=self.width-search_bar_vdd.lx(),
                            height=search_bar_vdd.height())

    def add_pins(self):
        pins_str = "bank_sel clk search clk_buf write_bar search_cbar sense_amp_en wordline_en ml_chb vdd gnd"
        self.add_pin_list(pins_str.split(' '))
