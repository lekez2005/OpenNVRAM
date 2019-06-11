from sram import sram
from modules.sotfet.sf_cam_bank import SfCamBank


class SfCam(sram):

    bank = bank_inst = None
    bank_count = 0
    power_rail_width = power_rail_pitch = 0

    def create_modules(self):
        self.bank = SfCamBank(word_size=self.word_size, num_words=self.num_words_per_bank,
                              words_per_row=self.words_per_row, name="bank")
        self.add_mod(self.bank)

        # Conditionally create the
        if self.num_banks > 1:
            self.create_multi_bank_modules()

        self.power_rail_width = self.bank.vdd_rail_width
        # Leave some extra space for the pitch
        self.power_rail_pitch = self.bank.vdd_rail_width + self.wide_m1_space

    def get_bank_connections(self, bank_num):
        connections = []
        for i in range(self.word_size):
            connections.append("DATA[{0}]".format(i))
        for i in range(self.word_size):
            connections.append("MASK[{0}]".format(i))
        for i in range(self.bank_addr_size):
            connections.append("ADDR[{0}]".format(i))
        if self.num_banks > 1:
            connections.append("bank_sel[{0}]".format(bank_num))
        else:
            connections.append("vdd")
        connections.extend(["clk", "search", "search_ref", "vdd", "gnd"])
        return connections

    def add_single_bank_modules(self):
        self.bank_inst = self.add_bank(0, [0, 0], -1, 1)
        self.width = self.bank_inst.rx()
        self.height = self.bank.height

    def add_single_bank_pins(self):
        """
        Add the top-level pins for a single bank SRAM with control.
        """
        m = None
        if m is None:
            return

        for i in range(self.word_size):
            self.copy_layout_pin(self.bank_inst, "DATA[{}]".format(i))
            self.copy_layout_pin(self.bank_inst, "MASK[{}]".format(i))

        for i in range(self.addr_size):
            self.copy_layout_pin(self.bank_inst, "ADDR[{}]".format(i))

        for pin in ["clk", "search", "search_ref"]:
            self.copy_layout_pin(self.bank_inst, pin, pin)

    def route_single_bank(self):
        """ Route a single bank SRAM """
        pass


    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i), "INOUT")
        for i in range(self.word_size):
            self.add_pin("MASK[{0}]".format(i), "INPUT")
        for i in range(self.addr_size):
            self.add_pin("ADDR[{0}]".format(i), "INPUT")

        self.add_pin_list(["search", "search_ref", "clk"], "INPUT")

        self.add_pin("vdd", "POWER")
        self.add_pin("gnd", "GROUND")

    def offset_all_coordinates(self):
        pass

    def add_lvs_correspondence_points(self):
        pass
