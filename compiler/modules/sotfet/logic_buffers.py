import debug
from base import design
from base.vector import vector
from globals import OPTS
from modules.buffer_stage import BufferStage
from modules.logic_buffer import LogicBuffer
from pgates.pinv import pinv
from pgates.pnand2 import pnand2


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

    nand = inv = clk_buf = clk_bar = write_buf = sense_amp_buf = wordline_buf = chb_buf = None
    clk_buf_inst = clk_bar_inst = None
    write_inst = search_inst = write_buf_inst = sense_amp_buf_inst = wordline_buf_inst = chb_buf_inst = None

    def __init__(self, contact_nwell=True, contact_pwell=True):
        design.design.__init__(self, self.name)
        debug.info(2, "Create Logic Buffers gate")

        self.height = OPTS.logic_buffers_height
        self.contact_pwell = contact_pwell
        self.contact_nwell = contact_nwell

        self.create_layout()
        self.create_modules()
        self.width = self.chb_buf_inst.rx()

    def create_layout(self):
        self.add_pins()
        self.create_modules()
        self.add_modules()

    def create_modules(self):
        common_args = {
            'height': self.height,
            'contact_nwell': self.contact_nwell,
            'contact_pwell': self.contact_pwell,
        }
        buffer_args = common_args.copy()
        buffer_args.update(route_outputs=False)

        logic_args = buffer_args.copy()
        logic_args.update(route_inputs=False)

        self.nand = pnand2(**common_args)
        self.add_mod(self.nand)

        self.inv = pinv(**common_args)
        self.add_mod(self.inv)

        self.clk_buf = BufferStage(buffer_stages=OPTS.clk_buffers, **buffer_args)
        self.add_mod(self.clk_buf)

        self.clk_bar = BufferStage(buffer_stages=OPTS.clk_bar_buffers, **buffer_args)
        self.add_mod(self.clk_bar)

        self.write_buf = BufferStage(buffer_stages=OPTS.write_buffers, **buffer_args)
        self.add_mod(self.write_buf)

        self.sense_amp_buf = LogicBuffer(buffer_stages=OPTS.sense_amp_buffers, logic="pnor2", **logic_args)
        self.add_mod(self.write_buf)

        self.wordline_buf = LogicBuffer(buffer_stages=OPTS.wordline_en_buffers, logic="pnor2", **logic_args)
        self.add_mod(self.wordline_buf)

        self.chb_buf = LogicBuffer(buffer_stages=OPTS.chb_buffers, logic="pnand2", **logic_args)
        self.add_mod(self.chb_buf)

    def add_modules(self):

        self.clk_buf_inst = self.add_inst("clk_buf", mod=self.clk_buf, offset=vector(0, 0))
        self.connect_inst(["clk", "clk_buf_bar", "clk_buf", "vdd", "gnd"])

        self.clk_bar_inst = self.add_inst("clk_bar", mod=self.clk_bar, offset=self.clk_buf_inst.lr())
        self.connect_inst(["clk", "clk_bar", "clk_bar_bar", "vdd", "gnd"])

        self.write_inst = self.add_inst("write", mod=self.nand, offset=self.clk_bar_inst.lr())
        self.connect_inst(["bank_sel", "search", "write", "vdd", "gnd"])

        self.search_inst = self.add_inst("search", mod=self.inv, offset=self.write_inst.lr())
        self.connect_inst(["write", "search_int", "vdd", "gnd"])

        self.write_buf_inst = self.add_inst("write_buf", mod=self.write_buf, offset=self.search_inst.lr())
        self.connect_inst(["write", "write_bar", "write_buf", "vdd", "gnd"])

        self.sense_amp_buf_inst = self.add_inst("sense_amp", mod=self.sense_amp_buf, offset=self.write_buf_inst.lr())
        self.connect_inst(["clk", "write", "sense_amp_bar", "sense_amp_en", "vdd", "gnd"])

        self.wordline_buf_inst = self.add_inst("wordline", mod=self.wordline_buf, offset=self.sense_amp_buf_inst.lr())
        self.connect_inst(["clk", "search_int", "wordline_bar", "wordline_en", "vdd", "gnd"])

        self.chb_buf_inst = self.add_inst("chb", mod=self.chb_buf, offset=self.wordline_buf_inst.lr())
        self.connect_inst(["clk", "search_int", "chb_buf", "ml_chb", "vdd", "gnd"])

    def add_pins(self):
        pins_str = "bank_sel clk search clk_buf clk_bar write_buf sense_amp_en wordline_en ml_chb vdd gnd"
        self.add_pin_list(pins_str.split(' '))
