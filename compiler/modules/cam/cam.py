from base.design import design
from globals import OPTS
from modules.baseline_bank import EXACT
from modules.shared_decoder.cmos_sram import CmosSram


class Cam(CmosSram):
    def create_layout(self):
        assert not OPTS.independent_banks, "Independent banks not supported for CAMs"
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
        if bank_num == 1:
            connections = bank_mod.connections_from_mod(connections,
                                                        [("search_out[", "search_out_1[")])
        return connections

    def get_schematic_pins(self):
        pins = super().get_schematic_pins()
        search_pins = [f"search_out[{row}]" for row in range(self.num_rows)]
        if self.num_banks == 2:
            search_pins.extend([f"search_out[{row}]" for row in range(self.num_rows)])

        index = pins.index(f"ADDR[{self.bank_addr_size - 1}]") + 1
        pins[index:index] = search_pins
        return pins
