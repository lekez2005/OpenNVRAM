from base.design import design
from globals import OPTS
from modules.baseline_bank import EXACT
from modules.baseline_sram import BaselineSram


class Cam(BaselineSram):

    def create_layout(self):
        assert (self.num_banks == 1 or OPTS.independent_banks), \
            "Dependent banks not supported for CAMs"
        super().create_layout()

    @staticmethod
    def get_bank_class():
        if getattr(OPTS, "bank_class"):
            return design.import_mod_class_from_str(OPTS.bank_class)
        from modules.cam.cam_bank import CamBank
        return CamBank

    def get_bank_connection_replacements(self):
        replacements = super().get_bank_connection_replacements()
        replacements.append(("search", "Web", EXACT))
        return replacements

    def get_bank_connections(self, bank_num, bank_mod):
        connections = super().get_bank_connections(bank_num, bank_mod)
        if bank_num > 0:
            replacements = [("search_out[", f"search_out_{bank_num}[")]
            connections = bank_mod.connections_from_mod(connections, replacements)
        return connections

    def copy_layout_pins(self):
        super().copy_layout_pins()
        self.copy_layout_pin(self.bank_inst, "search_ref")
        for bank_inst in self.bank_insts:
            conn = self.conns[self.insts.index(bank_inst)]
            for pin_index, pin_name in enumerate(bank_inst.mod.pins):
                if "search_out" in pin_name:
                    net = conn[pin_index]
                    self.copy_layout_pin(bank_inst, pin_name, net)

    def join_bank_controls(self):
        control_inputs = self.control_inputs
        self.control_inputs = ["search_ref"] + control_inputs
        super().join_bank_controls()
        self.control_inputs = control_inputs
