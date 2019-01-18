from base import contact
from base.vector import vector
from modules.bank_gate import BankGate
from modules.signal_gate import SignalGate


class CamBankGate(BankGate):

    def get_num_sel_signals(self):
        return 2  # bank_sel

    def setup_layout_constants(self):
        super(CamBankGate, self).setup_layout_constants()

        self.sel_all_y = self.bank_sel_y - self.rail_pitch

    def create_pins(self):
        self.add_pin("sel_all_banks")
        super(CamBankGate, self).create_pins()

    def add_instances(self):
        self.bank_sel_name = "sel"
        sig_gate = SignalGate([2], logic="or")
        self.add_mod(sig_gate)
        self.bank_sel = self.add_inst("bank_and", mod=sig_gate, offset=vector(self.x_offset, self.instances_y))
        self.connect_inst(["bank_sel", "sel_all_banks", self.bank_sel_name, "sel_bar", "vdd", "gnd"])
        self.x_offset += sig_gate.width


        super(CamBankGate, self).add_instances()

    def add_bank_sel(self):
        en_pin = self.bank_sel.get_pin("en")
        in_pin = self.bank_sel.get_pin("in")
        pins = [en_pin, in_pin]
        y_offsets = [self.bank_sel_y, self.bank_sel_y - self.rail_pitch]
        pin_names = ["bank_sel", "sel_all_banks"]
        for i in range(2):
            current_pin = pins[i]
            layout_pin_width = max(current_pin.rx(), self.metal1_minwidth_fill)
            self.add_layout_pin(pin_names[i], "metal1", offset=vector(0, y_offsets[i]), width=layout_pin_width)
            self.add_contact(contact.m1m2.layer_stack, offset=vector(current_pin.rx(), y_offsets[i]), rotate=90)
            self.add_rect("metal2", offset=vector(current_pin.lx(), y_offsets[i]), width=current_pin.width(),
                          height=current_pin.by() - y_offsets[i])

        # connect output pin to next input from the top
        adjacent_instance = self.module_insts[0]
        output_pin = self.bank_sel.get_pin("out")
        y_offset = output_pin.uy() + 0.5*contact.m1m2.second_layer_height - self.m2_width
        self.add_rect("metal2", offset=vector(output_pin.rx(), y_offset),
                      width=adjacent_instance.get_pin("en").lx() - output_pin.rx())

        # draw sel across
        last_instance = self.module_insts[-1]
        x_offset = adjacent_instance.get_pin("en").lx()
        self.add_rect("metal1", offset=vector(x_offset, self.bank_sel_y),
                      width=last_instance.get_pin("en").rx() - x_offset)



