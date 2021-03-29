import debug
from base import design
from base import utils
from base.design import NWELL
from base.vector import vector
from globals import OPTS
from modules.precharge import precharge, precharge_tap


class precharge_array(design.design):
    """
    Dynamically generated precharge array of all bitlines.  Cols is number
    of bit line columns, height is the height of the bit-cell array.
    """

    def __init__(self, columns, size=1):
        design.design.__init__(self, "precharge_array")
        debug.info(1, "Creating {0} with precharge size {1:.3g}".format(self.name, size))

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

        if OPTS.use_x_body_taps:
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
        self.child_insts = []
        for i in range(self.columns):
            name = "pre_column_{0}".format(i)
            offset = vector(self.bitcell_offsets[i], 0)
            inst=self.add_inst(name=name, mod=self.pc_cell, offset=offset)
            self.child_insts.append(inst)
            self.copy_layout_pin(inst, "bl", "bl[{0}]".format(i))
            self.copy_layout_pin(inst, "br", "br[{0}]".format(i))
            self.connect_inst(["bl[{0}]".format(i), "br[{0}]".format(i),
                               "en", "vdd"])
        for x_offset in self.tap_offsets:
            self.add_inst(self.body_tap.name, self.body_tap, offset=vector(x_offset, 0))
            self.connect_inst([])
        self.width = inst.rx()

        # fill nwell
        rect = self.pc_cell.get_layer_shapes(NWELL)[0]
        enclosure = self.well_enclose_ptx_active
        self.add_rect(NWELL, offset=vector(-enclosure, rect.by()),
                      width=self.width + 2 * enclosure, height=rect.height)
