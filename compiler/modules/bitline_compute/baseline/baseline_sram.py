from base.vector import vector
from globals import OPTS
from modules.bitline_compute.bl_bank import BlBank
from modules.internal_decoder_bank import InternalDecoderBank
from sram import sram


class BaselineSram(sram):

    bank = bank_inst = None

    def create_layout(self):
        self.create_bank()

        self.bank_inst = self.add_inst("bank0", mod=self.bank, offset=vector(0, 0))

        self.connect_inst(self.get_bank_nets())

        self.copy_bank_pins()

        self.width = self.bank_inst.rx()
        self.height = self.bank_inst.uy()

    def create_bank(self):
        self.bank = InternalDecoderBank(name="bank", word_size=self.word_size, num_words=self.num_words,
                                        words_per_row=self.words_per_row)
        self.add_mod(self.bank)

    def get_bank_nets(self):
        nets = []

        for i in range(self.word_size):
            nets.append("DATA[{0}]".format(i))
            nets.append("MASK[{0}]".format(i))
        for i in range(self.addr_size):
            nets.append("ADDR[{0}]".format(i))

        bank_sel_conn = "bank_sel"
        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            nets.extend([bank_sel_conn, "read", "clk", "vdd", "gnd"])
            if OPTS.sense_trigger_delay > 0:
                nets.append("sense_trig")
        else:
            nets.extend([bank_sel_conn, "read", "clk", "sense_trig", "vdd", "gnd"])

        if OPTS.separate_vdd:
            nets.extend(self.bank.external_vdds)
        return nets

    def add_pins(self):
        """ Adding pins for Bank module"""
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i))
            self.add_pin("MASK[{0}]".format(i))
        for i in range(self.addr_size):
            self.add_pin("ADDR[{0}]".format(i))

        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            control_pins = ["read", "clk", "bank_sel", "vdd", "gnd"]
        else:
            control_pins = ["read", "clk", "bank_sel", "sense_trig", "vdd", "gnd"]
        for pin in control_pins:
            self.add_pin(pin)

        if OPTS.separate_vdd:
            self.add_pin_list(BlBank.external_vdds)
        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP and OPTS.sense_trigger_delay > 0:
            self.add_pin("sense_trig")

    def copy_bank_pins(self):
        for pin_name in self.bank.pins:
            self.copy_layout_pin(self.bank_inst, pin_name, pin_name)

    def add_lvs_correspondence_points(self):
        pass

