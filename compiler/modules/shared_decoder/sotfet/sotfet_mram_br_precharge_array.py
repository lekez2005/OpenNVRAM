import debug
from base.design import design
from base.vector import vector
from base.well_implant_fills import get_default_fill_layers
from modules.precharge_array import precharge_array
from tech import drc


class sotfet_mram_br_precharge_array(precharge_array):
    def __init__(self, columns, bank):
        design.__init__(self, "sotfet_mram_br_precharge_array")
        debug.info(1, "Creating {0}".format(self.name))

        self.columns = columns

        self.pc_cell = bank.precharge_array.pc_cell
        self.child_mod = self.pc_cell

        self.body_tap = bank.precharge_array.body_tap
        self.add_mod(self.body_tap)

        self.height = self.pc_cell.height

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_insts(self):
        """Creates a precharge array by horizontally tiling the precharge cell"""
        self.load_bitcell_offsets()
        self.child_insts = []
        for i in range(self.columns):
            name = "mod_{0}".format(i)
            offset = vector(self.bitcell_offsets[i] + self.pc_cell.width, 0)
            inst = self.add_inst(name=name,
                                 mod=self.pc_cell,
                                 offset=offset, mirror="MY")
            bl_pin = inst.get_pin("bl")
            self.add_layout_pin(text="br[{0}]".format(i),
                                layer="metal2",
                                offset=bl_pin.ll(),
                                width=drc["minwidth_metal2"],
                                height=bl_pin.height())
            br_pin = inst.get_pin("br")
            self.add_layout_pin(text="bl[{0}]".format(i),
                                layer="metal2",
                                offset=br_pin.ll(),
                                width=drc["minwidth_metal2"],
                                height=bl_pin.height())
            self.connect_inst(["br[{0}]".format(i), "bl[{0}]".format(i),
                               "en", "vdd"])
            self.child_insts.append(inst)
        for x_offset in self.tap_offsets:
            self.add_inst(self.body_tap.name, self.body_tap, offset=vector(x_offset, 0))
            self.connect_inst([])
        self.width = inst.rx()

        default_layers, default_purposes = get_default_fill_layers()

        for layer, purpose in zip(default_layers, default_purposes):
            rects = self.pc_cell.get_layer_shapes(layer, purpose)
            rects = list(filter(lambda x: x.width >= self.pc_cell.width, rects))
            if not rects:
                continue
            rect = max(rects, key=lambda x: x.width * x.height)
            self.add_rect(layer, offset=vector(0, rect.by()),
                          width=self.width - rect.lx(), height=rect.height)
