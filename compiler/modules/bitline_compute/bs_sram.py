from globals import OPTS
from modules.bitline_compute.bit_serial_alu import BitSerialALU
from modules.bitline_compute.bl_bank import BlBank
from modules.bitline_compute.bl_sram import BlSram


class BsSram(BlSram):

    def create_modules(self):
        self.bank = BlBank(name="bank", word_size=self.word_size, num_words=self.num_words,
                           words_per_row=self.words_per_row)
        self.add_mod(self.bank)

        self.alu = BitSerialALU(bank=self.bank, num_cols=self.num_cols)
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

        for word in range(self.num_cols):
            connections.extend(["c_val[{}]".format(word), "cin[{}]".format(word), "cout[{}]".format(word)])
            # connections.extend(["c_val[{}]".format(word)])

        connections.extend(["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor", "s_sum", "s_data", "s_cout",
                            "s_mask_in", "s_bus"])

        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            connections.extend(["mask_en", "sr_en", "clk_buf", "clk", "vdd", "gnd"])
        else:
            connections.extend(["mask_en", "sr_en", "clk", "vdd", "gnd"])
        return connections

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

        for word in range(self.num_cols):
            self.add_pin_list(["c_val[{}]".format(word), "cin[{}]".format(word), "cout[{}]".format(word)])

        self.add_pin_list(["dec_en_0", "dec_en_1", "sense_amp_ref"])
        self.add_pin_list(["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor", "s_sum", "s_data", "s_cout"])
        self.add_pin_list(["s_mask_in", "s_bus"])

        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            for pin in ["read", "bank_sel", "mask_en", "sr_en", "clk", "vdd", "gnd"]:
                self.add_pin(pin)
        else:
            for pin in ["read", "bank_sel", "sense_trig", "diff", "diffb", "mask_en", "sr_en", "clk", "vdd", "gnd"]:
                self.add_pin(pin)

        for col in range(self.num_cols):
            self.add_pin("and[{}]".format(col))
            self.add_pin("nor[{}]".format(col))

        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP and OPTS.sense_trigger_delay > 0:
            self.add_pin("sense_trig")

    def copy_alu_pins(self):
        for col in range(self.num_cols):
            self.copy_layout_pin(self.alu_inst, "data_in[{}]".format(col), "DATA[{}]".format(col))
            self.copy_layout_pin(self.alu_inst, "mask_in[{}]".format(col), "MASK[{}]".format(col))

        for word in range(self.num_cols):
            self.copy_layout_pin(self.alu_inst, "c_val[{}]".format(word), "c_val[{}]".format(word))
            self.copy_layout_pin(self.alu_inst, "cin[{}]".format(word), "cin[{}]".format(word))
            self.copy_layout_pin(self.alu_inst, "cout[{}]".format(word), "cout[{}]".format(word))

        sel_names = ("s_and s_data_in s_nand s_nor s_or s_xnor s_xor "
                     "s_add s_cout s_mask_in s_bus mask_en sr_en ").split() # TODO renable when pins are added to layout
        #             "s_add s_cout s_mask_in s_bus ").split()

        for pin_name in sel_names:
            dest_name = pin_name
            if pin_name == "s_add":
                dest_name = "s_sum"
            elif pin_name == "s_data_in":
                dest_name = "s_data"
            self.copy_layout_pin(self.alu_inst, pin_name, dest_name)
