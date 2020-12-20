import debug
from base import design
from base import utils
from base.vector import vector
from modules.precharge import precharge, precharge_tap
from tech import drc


class precharge_array(design.design):
    """
    Dynamically generated precharge array of all bitlines.  Cols is number
    of bit line columns, height is the height of the bit-cell array.
    """

    def __init__(self, columns, size=1):
        design.design.__init__(self, "precharge_array")
        debug.info(1, "Creating {0}".format(self.name))

        self.columns = columns
        self.size = size
        self.create_modules()

        self.height = self.pc_cell.height

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def create_modules(self):
        self.pc_cell = precharge(name="precharge", size=self.size)
        self.add_mod(self.pc_cell)

        self.body_tap = precharge_tap(self.pc_cell)
        self.add_mod(self.body_tap)

    def add_pins(self):
        """Adds pins for spice file"""
        for i in range(self.columns):
            self.add_pin("bl[{0}]".format(i))
            self.add_pin("br[{0}]".format(i))
        self.add_pin("en")
        self.add_pin("vdd")

    def create_layout(self):
        self.add_insts()
        for vdd_pin in self.pc_cell.get_pins("vdd"):
            self.add_layout_pin(text="vdd", layer=vdd_pin.layer, offset=vdd_pin.ll(),
                                width=self.width, height=vdd_pin.height())
        en_pin = self.pc_cell.get_pin("en")
        self.add_layout_pin(text="en",
                            layer=en_pin.layer,
                            offset=en_pin.ll(),
                            width=self.width,
                            height=en_pin.height())
        

    def add_insts(self):
        """Creates a precharge array by horizontally tiling the precharge cell"""
        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.columns)
        for i in range(self.columns):
            name = "pre_column_{0}".format(i)
            offset = vector(self.bitcell_offsets[i], 0)
            inst=self.add_inst(name=name,
                          mod=self.pc_cell,
                          offset=offset)
            bl_pin = inst.get_pin("bl")
            self.add_layout_pin(text="bl[{0}]".format(i),
                                layer="metal2",
                                offset=bl_pin.ll(),
                                width=drc["minwidth_metal2"],
                                height=bl_pin.height())
            br_pin = inst.get_pin("br") 
            self.add_layout_pin(text="br[{0}]".format(i),
                                layer="metal2",
                                offset=br_pin.ll(),
                                width=drc["minwidth_metal2"],
                                height=bl_pin.height())
            self.connect_inst(["bl[{0}]".format(i), "br[{0}]".format(i),
                               "en", "vdd"])
        for x_offset in self.tap_offsets:
            self.add_inst(self.body_tap.name, self.body_tap, offset=vector(x_offset, 0))
            self.connect_inst([])
        self.width = inst.rx()
        layers = ["nwell"]
        purposes = ["drawing"]
        for i in range(1):
            rect = self.pc_cell.get_layer_shapes(layers[i], purposes[i])[0]
            self.add_rect(layers[i], offset=vector(0, rect.by()),
                          width=self.width+self.well_enclose_implant, height=rect.height)

