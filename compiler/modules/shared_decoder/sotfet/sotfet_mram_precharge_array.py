import debug
from base.design import design
from globals import OPTS
from modules.precharge import precharge_tap
from modules.precharge_array import precharge_array


class sotfet_mram_precharge_array(precharge_array):
    def __init__(self, columns, size=1):
        design.__init__(self, "sotfet_mram_precharge_array")
        debug.info(1, "Creating {0}".format(self.name))

        self.columns = columns

        c = __import__(OPTS.precharge)
        self.pc_cell = getattr(c, OPTS.precharge)(name="sotfet_mram_precharge", size=size)
        self.add_mod(self.pc_cell)

        self.body_tap = precharge_tap(self.pc_cell)
        self.add_mod(self.body_tap)

        self.height = self.pc_cell.height

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()
