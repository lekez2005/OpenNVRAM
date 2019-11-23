import debug
from base import design, utils
from base.contact import contact
from base.vector import vector
from modules import body_tap as mod_body_tap
from modules.sotfet.sf_bitline_buffer import SfBitlineBuffer
from tech import drc


class BitlineBufferTap(design.design):
    bitline_buffer = None

    def __init__(self, bitline_buffer):
        super().__init__("bitline_buffer_tap")

        self.bitline_buffer = bitline_buffer

        self.create_layout()

    def create_layout(self):

        bitcell_tap = mod_body_tap.body_tap
        self.width = bitcell_tap.width
        self.height = self.bitline_buffer.height

        # add poly dummies
        poly_allowance = 0.5*self.poly_to_field_poly
        x_offsets = [self.poly_space + 0.5*self.poly_width,
                     self.width-(self.poly_space + 0.5*self.poly_width) - self.poly_width]
        for x_offset in x_offsets:
            self.add_rect("po_dummy", offset=vector(x_offset, poly_allowance),
                          height=self.height-2*poly_allowance, width=self.poly_width)

        # fill nwell
        top_well = self.bitline_buffer.top_nwell
        bot_well = self.bitline_buffer.bot_nwell
        self.add_rect("nwell", offset=vector(0, bot_well), width=self.width, height=top_well-bot_well)

        vdd_pin = self.bitline_buffer.get_pin("vdd")
        dummy_space = x_offsets[1] - x_offsets[0] - self.poly_width  # space between poly
        active_width = dummy_space - 2*self.poly_to_active
        active_height = utils.ceil(drc["minarea_cont_active_thin"]/active_width)

        # add nwell contact

        self.add_rect_center("active", offset=vector(0.5*self.width, vdd_pin.cy()), width=active_width,
                             height=active_height)

        implant_width = self.width + 2*self.bitline_buffer.implant_x
        implant_height = max(active_height + 2*self.implant_enclose_active,
                             utils.ceil(drc["minarea_cont_active_thin"] / implant_width))

        self.add_rect_center("nimplant", offset=vector(0.5*self.width, vdd_pin.cy()), width=implant_width,
                             height=implant_height)

        num_contacts = self.calculate_num_contacts(active_height)
        self.add_contact_center(contact.active_layers, offset=vector(0.5*self.width, vdd_pin.cy()),
                                size=[1, num_contacts])

        # psub contact
        bottom_nimplant = min(self.bitline_buffer.get_layer_shapes("nimplant"), key=lambda x: x.by())
        implant_top = bottom_nimplant.uy() - self.implant_space
        implant_bottom = implant_top - implant_height
        implant_x = 0.5*(self.width - implant_width)
        self.add_rect("pimplant", offset=vector(implant_x, implant_bottom), width=implant_width, height=implant_height)

        center_y = implant_bottom+0.5*implant_height
        self.add_rect_center("active", offset=vector(0.5 * self.width, center_y),
                             width=active_width, height=active_height)

        cont = self.add_contact_center(contact.active_layers, offset=vector(0.5 * self.width, center_y),
                                       size=[1, num_contacts])
        gnd_pin = min(self.bitline_buffer.get_pins("gnd"), key=lambda x: x.by())
        self.add_rect("metal1", offset=vector(0.5*self.width - 0.5*gnd_pin.height(), cont.by()),
                      width=gnd_pin.height(), height=gnd_pin.by()-cont.by())



        # fill pins
        pin_names = ["vdd", "gnd"]
        for pin_name in pin_names:
            for pin in self.bitline_buffer.get_pins(pin_name):
                self.add_rect(pin.layer, offset=vector(0, pin.by()), width=self.width, height=pin.height())


class SfBitlineBufferArray(design.design):
    """
    Bitline driver buffers, should be a cascade of two inverters
    """
    mod_insts = []
    body_tap_insts = []
    bitcell_offsets = tap_offsets = []

    def __init__(self, word_size):

        design.design.__init__(self, "SfBitlineBufferArray")
        debug.info(1, "Creating {0}".format(self.name))

        self.word_size = word_size
        self.words_per_row = 1
        self.columns = self.words_per_row * self.word_size

        self.create_layout()

    def create_layout(self):
        self.add_pins()
        self.create_modules()
        self.create_array()

        self.width = max(self.mod_insts[-1].rx(), self.body_tap_insts[-1].rx())
        self.height = self.mod_insts[-1].uy()

        self.add_layout_pins()
        self.add_poly_dummy()

    def create_modules(self):
        self.bitline_buffer = SfBitlineBuffer()
        self.add_mod(self.bitline_buffer)
        self.body_tap = BitlineBufferTap(self.bitline_buffer)
        self.add_mod(self.body_tap)

    def create_array(self):

        (self.bitcell_offsets, self.tap_offsets) = utils.get_tap_positions(self.columns)
        for i in range(0, self.columns):
            name = "bitline_buffer{}".format(i)
            base = vector(self.bitcell_offsets[i], 0)

            instance = self.add_inst(name=name, mod=self.bitline_buffer, offset=base)
            self.mod_insts.append(instance)

            connection_str = "bl_in[{col}] br_in[{col}] bl_out[{col}] br_out[{col}] " \
                             "vdd gnd".format(col=i)

            self.connect_inst(connection_str.split(' '))
            # copy layout pins
            for pin_name in ["bl_in", "br_in", "bl_out", "bl_out"]:
                for j in range(2):
                    self.copy_layout_pin(instance, "{}".format(pin_name), "{}[{}]".format(pin_name, i))
        for x_offset in self.tap_offsets:
            self.body_tap_insts.append(self.add_inst(name=self.body_tap.name, mod=self.body_tap,
                                                     offset=vector(x_offset, 0)))
            self.connect_inst([])

    def add_poly_dummy(self):
        x_offset = self.width + self.poly_pitch - 0.5 * self.poly_width
        # get rightmost poly
        poly_rects = self.bitline_buffer.get_layer_shapes("po_dummy", purpose="po_dummy")
        right_most = max(poly_rects, key=lambda x: x.rx())
        all_right_rects = list(filter(lambda x: x.rx() == right_most.rx(), poly_rects))
        top_rect = max(all_right_rects, key=lambda x: x.uy())
        bottom_rect = min(all_right_rects, key=lambda x: x.uy())
        self.add_rect("po_dummy", offset=vector(x_offset, bottom_rect.by()), width=self.poly_width,
                      height=top_rect.uy() - bottom_rect.by())

    def add_pins(self):

        for i in range(self.word_size):
            self.add_pin("bl_in[{0}]".format(i))
            self.add_pin("br_in[{0}]".format(i))
        for i in range(0, self.columns, self.words_per_row):
            self.add_pin("bl_out[{0}]".format(i))
            self.add_pin("br_out[{0}]".format(i))

        self.add_pin_list(["vdd", "gnd"])

    def add_layout_pins(self):
        pin_names = ["vdd", "gnd"]
        for pin_name in pin_names:
            pins = self.mod_insts[0].get_pins(pin_name)
            for pin in pins:
                self.add_layout_pin(pin_name, pin.layer, offset=vector(0, pin.by()),
                                    width=self.width, height=pin.height())
