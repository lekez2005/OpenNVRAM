from base import design
from base.library_import import library_import
from base.vector import vector


@library_import
class sf_wordline_driver(design.design):
    """
    wordline driver
    """
    pin_names = "wl_in en vbias_p vbias_n wl vdd vdd_lo gnd".split()
    lib_name = "sot_wordline_driver"


class sot_wl_driver_array(design.design):
    """
    Creates a Wordline Driver using sf_wordline_driver cells
    """

    wl_driver = None
    module_insts = []

    def __init__(self, rows):
        design.design.__init__(self, "wordline_driver")
        self.rows = rows
        self.add_pins()
        self.create_layout()
        self.DRC_LVS()

    def add_pins(self):
        # inputs to wordline_driver.
        for i in range(self.rows):
            self.add_pin("in[{0}]".format(i))
        # Outputs from wordline_driver.
        for i in range(self.rows):
            self.add_pin("wl[{0}]".format(i))
        self.add_pin("en")
        self.add_pin_list(["vbias_p", "vbias_n", "vdd_lo", "vdd", "gnd"])

    def create_layout(self):
        self.create_modules()

        self.height = self.wl_driver.height * self.rows
        self.width = self.wl_driver.width

        self.add_modules()
        self.add_layout_pins()

    def create_modules(self):
        self.wl_driver = sf_wordline_driver()
        self.add_mod(self.wl_driver)

    def add_modules(self):
        for row in range(self.rows):
            if (row % 2) == 0:
                y_offset = self.wl_driver.height*(row + 1)
                mirror = "MX"

            else:
                y_offset = self.wl_driver.height*row
                mirror = "R0"
            # add logic buffer
            driver_inst = self.add_inst("driver{}".format(row), mod=self.wl_driver,
                                        offset=vector(0, y_offset), mirror=mirror)
            self.connect_inst(["in[{}]".format(row), "en", "vbias_p", "vbias_n", "wl[{}]".format(row), "vdd",
                               "vdd_lo", "gnd"])

            self.module_insts.append(driver_inst)

    def add_layout_pins(self):
        for pin_name in ["en", "vbias_n", "vbias_p"]:
            pin = self.wl_driver.get_pin(pin_name)
            self.add_layout_pin(pin_name, pin.layer, offset=pin.ll(), height=self.height, width=pin.width())

        for row in range(self.rows):
            self.copy_layout_pin(self.module_insts[row], "wl", "wl[{}]".format(row))
            for pin_name in ["vdd_lo", "gnd"]:
                self.copy_layout_pin(self.module_insts[row], pin_name, pin_name)

    def analytical_delay(self, slew, load=0):
        return self.wl_driver.analytical_delay(slew, load)

    def input_load(self):
        return self.wl_driver.logic_mod.input_load()
