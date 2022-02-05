import debug
from base.design import design
from globals import OPTS
from modules.precharge import precharge_tap
from modules.precharge_array import precharge_array


class sotfet_mram_precharge_array(precharge_array):
    def __init__(self, columns, size=1):
        design.__init__(self, "sotfet_mram_precharge_array")
        debug.info(1, "Creating %s with precharge size %.3g", self.name, size)

        self.columns = columns

        self.pc_cell = self.create_mod_from_str(OPTS.precharge,
                                                name="sotfet_mram_precharge", size=size)

        self.child_mod = self.pc_cell

        self.body_tap = precharge_tap(self.pc_cell)
        self.add_mod(self.body_tap)

        self.height = self.pc_cell.height

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()
