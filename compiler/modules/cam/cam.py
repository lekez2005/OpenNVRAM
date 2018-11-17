import cam_bank
import contact
import debug
import re
import sram
from vector import vector


class Cam(sram.sram):

    def compute_sizes(self):
        super(Cam, self).compute_sizes()
        if self.words_per_row > 1:
            debug.error("Only one word per row permitted for CAM", -1)

    def get_control_logic_names(self):
        return ["clk_buf", "s_en", "w_en", "search_en", "mw_en", "sel_all_banks", "sel_all_rows", "latch_tags",
                "matchline_chb"]

    def add_single_bank_pins(self):
        for i in range(self.word_size):
            self.copy_layout_pin(self.bank_inst, "DATA[{}]".format(i))
            self.copy_layout_pin(self.bank_inst, "MASK[{}]".format(i))

        for i in range(self.addr_size):
            self.copy_layout_pin(self.bank_inst, "ADDR[{}]".format(i))

        for (old, new) in zip(["csb", "web", "oeb", "seb", "mwb", "bcastb", "clk"],
                             ["CSb", "WEb", "OEb", "SEb", "MWb", "BCASTb", "clk"]):
            self.copy_layout_pin(self.control_logic_inst, old, new)

    def route_single_bank(self):
        control_logic_names = self.get_control_logic_names()
        for i in range(len(control_logic_names)):
            ctrl_pin = self.control_logic_inst.get_pin(control_logic_names[i])
            bank_pin = self.bank_inst.get_pin(control_logic_names[i])

            self.add_rect("metal3", offset=ctrl_pin.ul(), height=bank_pin.uy() - ctrl_pin.uy())
            self.add_rect("metal2", offset=bank_pin.lr(), width=ctrl_pin.rx() - bank_pin.rx())
            if control_logic_names[i] in ["search_en"]:
                self.add_contact(contact.m2m3.layer_stack, offset=vector(ctrl_pin.rx(), bank_pin.by()), rotate=90)
            else:
                self.add_contact(contact.m2m3.layer_stack,
                                 offset=vector(ctrl_pin.lx(), bank_pin.uy() - contact.m2m3.second_layer_height))

        # route bank_sel to vdd
        bank_sel_pin = self.bank_inst.get_pin("bank_sel")
        self.add_rect("metal1", offset=bank_sel_pin.ll(), width=self.bank_inst.rx() - bank_sel_pin.lx())
        self.add_contact(contact.m1m2.layer_stack, offset=vector(self.bank_inst.rx(), bank_sel_pin.by()),
                         size=[1, 2], rotate=90)

        self.route_one_bank_power()

    def route_two_banks(self):
        pass

    def route_four_banks(self):
        pass

    def create_modules(self):
        """ Create all the modules that will be used """

        # Create the control logic module
        self.control_logic = self.mod_control_logic(num_rows=self.num_rows)
        self.add_mod(self.control_logic)

        # Create the bank module (up to four are instantiated)
        self.bank = cam_bank.CamBank(word_size=self.word_size,
                         num_words=self.num_words_per_bank,
                         words_per_row=self.words_per_row,
                         name="bank")
        self.add_mod(self.bank)

        # Conditionally create the
        if self.num_banks > 1:
            self.create_multi_bank_modules()


    def add_pins(self):
        """ Add pins for entire CAM. """
        # These are used to create the physical pins too
        self.control_logic_inputs = ["CSb", "WEb", "OEb", "SEb", "MWb", "BCASTb", "clk"]
        self.control_logic_outputs = ["s_en", "w_en", "search_en", "mw_en", "sel_all_banks", "sel_all_rows",
                                      "latch_tags", "matchline_chb", "clk_buf"]

        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i), "INOUT")
        for i in range(self.word_size):
            self.add_pin("MASK[{0}]".format(i), "INPUT")
        for i in range(self.addr_size):
            self.add_pin("ADDR[{0}]".format(i), "INPUT")

        self.add_pin_list(["CSb", "WEb", "OEb", "SEb", "MWb", "BCASTb", "clk"], "INPUT")
        self.add_pin("vdd", "POWER")
        self.add_pin("gnd", "GROUND")

    def add_control_logic(self, position, rotate=0, mirror="R0"):
        """ Add and place control logic """
        self.control_logic_inst = self.add_inst(name="control",
                                              mod=self.control_logic,
                                              offset=position + vector(0, self.control_logic.height),
                                              mirror="MX",
                                              rotate=rotate)
        self.connect_inst(["CSb", "WEb", "OEb", "SEb", "MWb", "BCASTb", "clk"] +
                          ["clk_buf", "s_en", "w_en", "search_en", "mw_en", "sel_all_banks", "sel_all_rows",
                           "latch_tags", "matchline_chb"] +
                          ["vdd", "gnd"])

    def connect_inst(self, args, check=True):
        if self.insts[-1].name.startswith("bank"):
            args = []
            for i in range(self.word_size):
                args.append("DATA[{0}]".format(i))
            for i in range(self.word_size):
                args.append("MASK[{0}]".format(i))
            for i in range(self.bank_addr_size):
                args.append("ADDR[{0}]".format(i))
            args.append("sel_all_banks")
            if self.num_banks > 1:
                bank_name = self.insts[-1].name
                bank_num = re.match(".*bank(?P<bank_num>\d+)", bank_name).group('bank_num')
                args.append("bank_sel[{0}]".format(bank_num))
            else:
                args.append("vdd")
            args.extend(["clk_buf", "s_en", "w_en", "search_en", "matchline_chb", "mw_en", "sel_all_rows", "latch_tags",
                         "vdd", "gnd"])
        super(Cam, self).connect_inst(args, check)
