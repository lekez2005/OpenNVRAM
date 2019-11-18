from base import utils
from base.contact import m1m2, m2m3
from base.vector import vector
from globals import OPTS
from modules.sotfet.sf_cam_bank import SfCamBank
from sram import sram
from tech import drc


class SfCam(sram):

    bank = bank_inst = None
    bank_count = 0
    power_rail_width = power_rail_pitch = 0

    def create_modules(self):
        self.separate_vdd = OPTS.separate_vdd if hasattr(OPTS, 'separate_vdd') else False
        self.create_bank_module()

        # Conditionally create the
        if self.num_banks > 1:
            self.create_multi_bank_modules()

        self.power_rail_width = self.bank.vdd_rail_width
        # Leave some extra space for the pitch
        self.power_rail_pitch = self.bank.vdd_rail_width + self.wide_m1_space

    def create_bank_module(self):
        self.bank = SfCamBank(word_size=self.word_size, num_words=self.num_words_per_bank,
                              words_per_row=self.words_per_row, name="bank")
        self.add_mod(self.bank)

    def get_bank_connections(self, bank_num):
        connections = []
        for i in range(self.word_size):
            connections.append("DATA[{0}]".format(i))
        for i in range(self.word_size):
            connections.append("MASK[{0}]".format(i))
        for i in range(self.word_size):
            connections.append("search_out[{0}]".format(i))
        for i in range(self.bank_addr_size):
            connections.append("ADDR[{0}]".format(i))
        if self.num_banks > 1:
            connections.append("bank_sel[{0}]".format(bank_num))
        else:
            bank_sel = "vdd_logic_buffers" if self.separate_vdd else "vdd"
            connections.append(bank_sel)
        if self.separate_vdd:
            vdd_pins = ["vdd_wordline", "vdd_decoder", "vdd_logic_buffers", "vdd_data_flops",
                        "vdd_bitline_buffer", "vdd_bitline_logic", "vdd_sense_amp"]
            self.add_pin_list(vdd_pins)
            vdd_connections = ["vdd"] + vdd_pins
        else:
            vdd_connections = ["vdd"]
        connections.extend(["clk", "search", "search_ref"] + vdd_connections + ["gnd"] + self.add_wordline_connections())
        return connections

    @staticmethod
    def add_wordline_connections():
        return ["vbias_n", "vbias_p"]

    def add_single_bank_modules(self):
        self.bank_inst = self.add_bank(0, [0, 0], -1, 1)
        self.width = self.bank_inst.rx()
        self.height = self.bank.height

    def add_single_bank_pins(self):
        """
        Add the top-level pins for a single bank SRAM with control.
        """

        for i in range(self.word_size):
            self.copy_layout_pin(self.bank_inst, "DATA[{}]".format(i))
            self.copy_layout_pin(self.bank_inst, "MASK[{}]".format(i))
        for row in range(self.num_rows):
            self.copy_layout_pin(self.bank_inst, "search_out[{}]".format(row))

        for i in range(self.addr_size):
            self.copy_layout_pin(self.bank_inst, "ADDR[{}]".format(i))

        for pin in ["clk", "search", "search_ref"] + self.add_wordline_connections():
            self.copy_layout_pin(self.bank_inst, pin, pin)

        for pin_name in ["vdd", "gnd"]:
            self.copy_layout_pin(self.bank_inst, pin_name, pin_name)

    def route_single_bank(self):
        """ Route a single bank SRAM """
        # route bank_sel to vdd
        bank_sel_pin = self.bank_inst.get_pin("bank_sel")
        (ll, ur) = utils.get_pin_rect(self.bank.logic_buffers_inst.get_pin("vdd"), [self.bank_inst])
        self.add_rect("metal3", offset=vector(bank_sel_pin.rx()-0.5*self.m3_width, ll[1]),
                      height=bank_sel_pin.uy()-ll[1])
        m2_fill_height = drc["minside_metal1_contact"]
        m2_fill_width = utils.ceil(self.minarea_metal1_contact / m2_fill_height)
        cy = 0.5*(ll[1] + ur[1])
        self.add_rect_center("metal2", offset=vector(bank_sel_pin.rx(), cy), width=m2_fill_width,
                             height=m2_fill_height)
        self.add_contact_center(m2m3.layer_stack, offset=vector(bank_sel_pin.rx(), cy))
        self.add_contact_center(m1m2.layer_stack, offset=vector(bank_sel_pin.rx(), cy), size=[1, 2])

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i), "INOUT")
        for i in range(self.word_size):
            self.add_pin("MASK[{0}]".format(i), "INPUT")
        for i in range(self.addr_size):
            self.add_pin("ADDR[{0}]".format(i), "INPUT")
        for row in range(self.num_rows):
            self.add_pin("search_out[{0}]".format(row), "OUTPUT")

        self.add_pin_list(["search", "search_ref", "clk"], "INPUT")

        self.add_wordline_pins()

        self.add_pin("vdd", "POWER")
        self.add_pin("gnd", "GROUND")

    def add_wordline_pins(self):
        self.add_pin_list(["vbias_n", "vbias_p"], "INPUT")

    def offset_all_coordinates(self):
        pass

    def add_lvs_correspondence_points(self):
        pass
