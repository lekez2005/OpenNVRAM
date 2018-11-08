import contact
import design
from tech import drc
import debug
from vector import vector
from globals import OPTS


class address_mux_array(design.design):
    """
    Array of 2-1 mux to decide between address decoder output and match tags for enabling wordline driver
    """

    def __init__(self, rows):
        design.design.__init__(self, "address_mux_array")
        debug.info(1, "Creating {0}".format(self.name))

        c = reload(__import__(OPTS.address_mux))
        self.mod_mux = getattr(c, OPTS.address_mux)
        self.mux = self.mod_mux()
        self.add_mod(self.mux)

        self.rows = rows
        self.mux_insts = [None]*rows

        self.width = self.mux.width
        self.height = self.rows * self.mux.height

        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_pins(self):
        for i in range(self.rows):
            self.add_pin("dec[{0}]".format(i))
            self.add_pin("tag[{0}]".format(i))
            self.add_pin("out[{0}]".format(i))
        self.add_pin("sel")
        self.add_pin("sel_bar")
        self.add_pin("sel_all")
        self.add_pin("sel_all_bar")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_layout(self):
        for row in range(self.rows):
            name = "addr_mux_{}".format(row)
            y_offset = row * self.mux.height
            if row % 2 == 0:
                y_offset += self.mux.height
                mirror = "MX"
            else:
                mirror = "R0"
            offset = vector(0, y_offset)

            self.mux_insts[row] = self.add_inst(name=name, mod=self.mux, offset=offset, mirror=mirror)

            self.connect_inst(["dec[{0}]".format(row),
                               "tag[{0}]".format(row),
                               "sel", "sel_bar", "sel_all", "sel_all_bar", "out[{0}]".format(row), "vdd", "gnd"])
        self.add_layout_pins()

    def add_layout_pins(self):
        for row in range(self.rows):
            mux_inst = self.mux_insts[row]
            self.copy_layout_pin(mux_inst, "in[0]", "dec[{0}]".format(row))
            self.copy_layout_pin(mux_inst, "in[1]", "tag[{0}]".format(row))
            self.copy_layout_pin(mux_inst, "out", "out[{0}]".format(row))

            if row % 2 == 0 or row == self.rows - 1:
                self.copy_layout_pin(mux_inst, "vdd", "vdd")
                self.copy_layout_pin(mux_inst, "gnd", "gnd")

        mux_inst = self.mux_insts[0]

        pins = ["sel", "sel_bar", "sel_all_bar", "sel_all"]

        for i in range(4):
            self.copy_layout_pin(mux_inst, pins[i], pins[i])



