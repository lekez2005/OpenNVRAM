from base.vector import vector
from globals import OPTS
from modules.bitline_compute.baseline.baseline_sram import BaselineSram
from modules.bitline_compute.bitline_alu import BitlineALU
from modules.bitline_compute.bl_bank import BlBank


class BlSram(BaselineSram):

    bank = bank_inst = None

    alu = alu_inst = None

    alu_num_words = 1

    def compute_sizes(self):
        super().compute_sizes()
        self.alu_num_words = int(self.num_cols / OPTS.alu_word_size)

    def create_layout(self):

        self.create_modules()
        self.add_modules()

        self.copy_bank_pins()
        self.copy_alu_pins()

        self.width = self.bank_inst.rx()
        self.height = self.bank_inst.uy()

    def create_modules(self):
        self.bank = BlBank(name="bank", word_size=self.word_size, num_words=self.num_words,
                           words_per_row=self.words_per_row)
        self.add_mod(self.bank)

        self.alu = BitlineALU(bank=self.bank, num_cols=self.num_cols, word_size=OPTS.alu_word_size,
                              cells_per_group=OPTS.alu_cells_per_group, inverter_size=OPTS.alu_inverter_size)
        self.add_mod(self.alu)

    def get_alu_connections(self):
        connections = []
        for col in range(self.num_cols):
            connections.append("DATA[{}]".format(col))
            connections.append("MASK[{}]".format(col))
            connections.append("and[{}]".format(col))
            connections.append("nor[{}]".format(col))

        for col in range(self.num_cols):
            connections.append("bus[{}]".format(col))

        for col in range(self.num_cols):
            connections.append("mask_bar[{}]".format(col))

        for word in range(self.alu_num_words):
            connections.extend(["cin[{}]".format(word), "cout[{}]".format(word)])

        connections.extend(["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor", "s_sum", "s_data",
                            "s_mask_in", "s_bus", "s_shift", "s_sr", "s_lsb", "s_msb"])
        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            connections.extend(["sr_en", "clk_buf", "clk", "vdd", "gnd"])
        else:
            connections.extend(["sr_en", "clk", "vdd", "gnd"])
        return connections

    def add_modules(self):
        self.alu_inst = self.add_inst("alu", mod=self.alu, offset=vector(0, 0))

        self.connect_inst(self.get_alu_connections())

        and_pin = self.bank.get_pin("and[0]")
        y_offset = self.alu_inst.uy() - and_pin.by()
        self.bank_inst = self.add_inst("bank0", mod=self.bank, offset=vector(0, y_offset))

        connections = []

        for i in range(self.word_size):
            connections.append("bus[{0}]".format(i))
            connections.append("mask_bar[{0}]".format(i))
        for i in range(self.addr_size):
            connections.append("ADDR[{0}]".format(i))
            connections.append("ADDR_1[{0}]".format(i))

        connections.extend(["dec_en_0", "dec_en_1", "sense_amp_ref"])

        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            connections.extend(["bank_sel", "read", "clk", "clk_buf", "vdd", "gnd"])
        else:
            connections.extend(["bank_sel", "read", "clk", "sense_trig", "diff", "diffb", "clk_buf", "vdd", "gnd"])

        for col in range(self.num_cols):
            connections.append("and[{}]".format(col))
            connections.append("nor[{}]".format(col))

        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP and OPTS.sense_trigger_delay > 0:
            connections.append("sense_trig")

        self.connect_inst(connections)

    def add_pins(self):
        """ Adding pins for Bank module"""
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i))
            self.add_pin("MASK[{0}]".format(i))

        for col in range(self.num_cols):
            self.add_pin("bus[{}]".format(col))

        for i in range(self.addr_size):
            self.add_pin("ADDR[{0}]".format(i))
            self.add_pin("ADDR_1[{0}]".format(i))

        for word in range(self.alu_num_words):
            self.add_pin_list(["cin[{}]".format(word), "cout[{}]".format(word)])

        self.add_pin_list(["dec_en_0", "dec_en_1", "sense_amp_ref"])
        self.add_pin_list(["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor", "s_sum", "s_data"])
        self.add_pin_list(["s_mask_in", "s_bus", "s_shift", "s_sr", "s_lsb", "s_msb"])
        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            for pin in ["read", "bank_sel", "sr_en", "clk", "vdd", "gnd"]:
                self.add_pin(pin)
        else:
            for pin in ["read", "bank_sel", "sense_trig", "diff", "diffb", "sr_en", "clk", "vdd", "gnd"]:
                self.add_pin(pin)

        for col in range(self.num_cols):
            self.add_pin("and[{}]".format(col))
            self.add_pin("nor[{}]".format(col))

        if OPTS.separate_vdd:
            self.add_pin_list(BlBank.external_vdds)
        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP and OPTS.sense_trigger_delay > 0:
            self.add_pin("sense_trig")

    def copy_bank_pins(self):
        skipped_pins = ["mask_in_bar", "clk_buf"]
        for pin_name in self.bank.pins:
            ignored = False
            for skipped_pin in skipped_pins:
                if pin_name.startswith(skipped_pin):
                    ignored = True
                    break

            if not ignored:
                new_pin_name = pin_name
                if pin_name.startswith("DATA"):
                    new_pin_name = pin_name.replace("DATA", "bus")

                self.copy_layout_pin(self.bank_inst, pin_name, new_pin_name)

    def copy_alu_pins(self):
        for col in range(self.num_cols):
            self.copy_layout_pin(self.alu_inst, "data_in[{}]".format(col), "DATA[{}]".format(col))
            self.copy_layout_pin(self.alu_inst, "mask_in[{}]".format(col), "MASK[{}]".format(col))

        for word in range(self.alu_num_words):
            self.copy_layout_pin(self.alu_inst, "cin[{}]".format(word), "cin[{}]".format(word))
            self.copy_layout_pin(self.alu_inst, "cout[{}]".format(word), "cout[{}]".format(word))

        sel_names = ("s_and s_data_in s_nand s_nor s_or s_xnor s_xor "
                     "s_add s_mask_in s_bus s_shift s_sr s_lsb s_msb sr_en ").split()

        for pin_name in sel_names:
            dest_name = pin_name
            if pin_name == "s_add":
                dest_name = "s_sum"
            elif pin_name == "s_data_in":
                dest_name = "s_data"
            self.copy_layout_pin(self.alu_inst, pin_name, dest_name)

    def add_lvs_correspondence_points(self):
        pass
