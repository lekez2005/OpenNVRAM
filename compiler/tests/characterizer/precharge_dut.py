from base import utils
from base.contact import m1m2
from base.design import design, METAL1, METAL2, PIMP, NWELL, NIMP, METAL3
from base.vector import vector
from base.well_implant_fills import create_wells_and_implants_fills
from globals import OPTS
from modules.bitcell_array import bitcell_array
from modules.buffer_stage import BufferStage
from modules.precharge import precharge
from pgates.pinv import pinv
from tech import parameter, drc

c = __import__(OPTS.bitcell)
bitcell = getattr(c, OPTS.bitcell)()


class InverterExtendContactActive(pinv):
    """Extend inverter active to prevent minimum spacing issues"""

    def setup_layout_constants(self):
        super().setup_layout_constants()
        # ensure width is divisible by 2
        self.width = utils.ceil_2x_grid(self.width)
        self.mid_x = utils.round_to_grid(self.mid_x)
        self.implant_width = max(bitcell.width, self.implant_width)
        self.nwell_width = bitcell.width + 2 * self.well_enclose_active

    def calculate_body_contacts(self):
        width = self.width
        self.width = bitcell.width
        super().calculate_body_contacts()
        self.width = width

    def add_body_contacts(self):
        width = self.width
        self.width = bitcell.width
        super().add_body_contacts()
        self.width = width


class PrechargeNoEn(precharge):
    """Precharge cell without extending en pin across cell and no nwell contacts"""

    def add_layout_pin_center_rect(self, text, layer, offset, width=None, height=None):
        """Prevent adding en pin"""
        if text == "en":
            return None
        return super().add_layout_pin_center_rect(text, layer, offset, width, height)

    def add_layout_pin(self, text, layer, offset, width=None, height=None):
        if text == "en" and width >= self.width:
            return None
        return super().add_layout_pin(text, layer, offset, width, height)

    def connect_input_gates(self):
        super().connect_input_gates()
        en_m1_rect = self.en_m1_rect
        for layer in [METAL1, METAL3]:
            self.add_layout_pin("en", layer, offset=en_m1_rect.offset,
                                width=en_m1_rect.width)

    def add_active_contacts(self):
        super().add_active_contacts()
        # extend vdd to the inverter vdd
        vdd_x = [0, self.width - self.m1_width]
        for x_offset in vdd_x:
            self.add_rect(METAL1, offset=vector(x_offset, self.contact_y),
                          height=self.height - self.contact_y)

    def add_nwell_contacts(self):
        pass


class PrechargeInverter(design):
    def __init__(self, precharge_size):
        self.name = "precharge_cell_{:.4g}".format(precharge_size).replace(".", "__")
        self.precharge_size = precharge_size
        super().__init__(self.name)

        self.create_layout()

    def create_layout(self):
        self.add_pins()

        self.width = bitcell.width
        self.create_inverter()
        self.add_inverter()
        self.add_precharge()

        # en_bar to en
        en_bar = self.inv_inst.get_pin("Z")
        en = self.precharge_inst.get_pin("en")

        inverter_m2 = self.inv_inst.get_layer_shapes(METAL2, recursive=True)
        # find m2 on same row as en_bar (should be a drain connection)
        valid_m2 = list(filter(lambda x: x.by() <= en_bar.uy() <= x.uy(),
                               inverter_m2))
        # height should be greater than width aka via
        valid_m2 = list(filter(lambda x: x.height > x.width,
                               valid_m2))
        # find closest to middle
        m2_rect = min(valid_m2, key=lambda x: abs(x.cx() - en.cx()))

        self.add_rect(METAL2, offset=m2_rect.ll(), height=en.by() - m2_rect.by() + self.m2_width)
        self.add_rect(METAL2, offset=vector(en.cx(), en.by()),
                      width=m2_rect.cx() - en.cx())

        self.copy_layout_pin(self.precharge_inst, "bl", "bl")
        self.copy_layout_pin(self.precharge_inst, "br", "br")

        self.height = self.precharge_inst.uy()

    def create_inverter(self):
        # create smallest height inverter
        height = bitcell.height * 0.5
        while True:
            try:
                self.inv = InverterExtendContactActive(size=1, height=height,
                                                       contact_nwell=True,
                                                       contact_pwell=True)
                self.add_mod(self.inv)
                break
            except AttributeError:
                height *= 1.2

    def add_inverter(self):
        nimp_rect = max(self.inv.get_layer_shapes(NIMP),
                        key=lambda x: x.width * x.height)
        x_offset = -nimp_rect.lx()

        self.inv_inst = self.add_inst("inv", mod=self.inv, offset=vector(x_offset, 0))
        self.connect_inst(["en", "en_bar", "vdd", "gnd"])

        for pin_name in ["vdd", "gnd"]:
            self.copy_layout_pin(self.inv_inst, pin_name, pin_name)

        # en pin
        a_pin = self.inv_inst.get_pin("A")
        self.add_contact_center(layers=m1m2.layer_stack, offset=a_pin.center(),
                                rotate=90)
        self.add_layout_pin_center_rect("en", METAL2, offset=a_pin.center())

    def add_precharge(self):
        name = "precharge_no_en_{:.4g}".format(self.precharge_size).replace(".", "__")
        actual_size = self.precharge_size / parameter["beta"]

        self.precharge = PrechargeNoEn(name, size=actual_size)
        self.add_mod(self.precharge)

        y_offset = self.inv_inst.uy() + self.precharge.height
        precharge_inst = self.add_inst("precharge", self.precharge,
                                       offset=vector(0, y_offset),
                                       mirror="MX")
        self.precharge_inst = precharge_inst
        self.connect_inst(["bl", "br", "en_bar", "vdd"])

        self.fill_implants()

    def fill_implants(self):
        inverter_nimp = max(self.inv_inst.get_layer_shapes(NIMP),
                            key=lambda x: x.uy())
        precharge_pimp = min(self.precharge_inst.get_layer_shapes(PIMP),
                             key=lambda x: x.by())
        self.add_rect(PIMP, offset=vector(precharge_pimp.lx(), inverter_nimp.uy()),
                      width=precharge_pimp.width,
                      height=precharge_pimp.by() - inverter_nimp.uy())

    def add_pins(self):
        self.add_pin_list(["bl", "br", "en", "vdd", "gnd"])


class PrechargeArray(design):
    def __init__(self, precharge_size, num_elements):
        self.name = "precharge_array_{}_{:.4g}".format(num_elements, precharge_size)
        self.name = self.name.replace(".", "__")
        self.size = precharge_size
        self.columns = num_elements
        super().__init__(self.name)
        self.create_layout()

    def create_layout(self):
        self.add_pins()
        self.precharge_cell = PrechargeInverter(precharge_size=self.size)
        self.add_mod(self.precharge_cell)

        bitcell_array_class = self.import_mod_class_from_str(OPTS.bitcell_array)
        offsets = bitcell_array_class.calculate_x_offsets(num_cols=self.columns)
        (self.bitcell_offsets, self.tap_offsets, _) = offsets

        self.child_insts = []

        for i in range(self.columns):
            name = "pre_{0}".format(i)
            offset = vector(self.bitcell_offsets[i], 0)
            inst = self.add_inst(name=name, mod=self.precharge_cell,
                                 offset=offset)
            bl_name = "bl[{0}]".format(i)
            br_name = "br[{0}]".format(i)
            self.copy_layout_pin(inst, "bl", bl_name)
            self.copy_layout_pin(inst, "br", br_name)

            self.connect_inst([bl_name, br_name, "en", "vdd", "gnd"])
            self.child_insts.append(inst)

        self.width = self.insts[-1].rx()
        self.height = self.insts[0].height

        # Add vdd/gnd labels at the right edge so no degradation at the relevant cell
        # which is the rightmost precharge cell
        # en label should be on the left
        label_x_offsets = [0, self.width, self.width]
        pin_names = ["en", "vdd", "gnd"]
        for i in range(3):
            cell_pin = self.precharge_cell.get_pin(pin_names[i])
            self.add_rect(cell_pin.layer, offset=vector(0, cell_pin.by()),
                          width=self.width, height=cell_pin.height())
            # add min width pin
            self.add_layout_pin(pin_names[i], layer=cell_pin.layer,
                                offset=vector(label_x_offsets[i], cell_pin.by()),
                                height=cell_pin.height())

        # fill gaps
        inv_fill = create_wells_and_implants_fills(self.precharge_cell.inv,
                                                   self.precharge_cell.inv)

        # extend NWELL
        nwell_width = self.width + (self.precharge_cell.precharge.implant_width -
                                    bitcell.width)

        for layer, bottom, top, _, _ in inv_fill:
            width = nwell_width if layer == NWELL else self.width
            self.add_rect(layer, offset=vector(0, bottom),
                          width=width, height=top - bottom)

        precharge_fill = create_wells_and_implants_fills(self.precharge_cell.precharge,
                                                         self.precharge_cell.precharge)
        for layer, bottom, top, _, _ in precharge_fill:
            width = nwell_width if layer == NWELL else self.width
            y_offset = (self.precharge_cell.precharge_inst.by() +
                        self.precharge_cell.precharge.height - top)
            self.add_rect(layer, offset=vector(0, y_offset),
                          width=width, height=top - bottom)

    def add_pins(self):
        pins = []
        for i in range(self.columns):
            pins.extend(["bl[{}]".format(i), "br[{}]".format(i)])
        pins.extend(["en", "gnd", "vdd"])
        self.add_pin_list(pins)


class PrechargeDut(design):
    def __init__(self, num_elements, precharge_size, buffer_stages,
                 driver_wire_length=0, two_d=True):
        self.name = "precharge_dut_{}_{:.4g}".format(num_elements, precharge_size)
        self.name = self.name.replace(".", "__")
        super().__init__(self.name)
        self.buffer_stages = buffer_stages
        self.num_elements = num_elements
        self.precharge_size = precharge_size
        self.driver_wire_length = driver_wire_length
        self.two_d = two_d
        self.create_layout()

    def create_layout(self):
        self.add_pins()

        # Buffer stages
        min_tx_width = drc["minwidth_tx"]
        buffer_stages_sizes = [1e6 * x / min_tx_width for x in self.buffer_stages]
        buffer = BufferStage(buffer_stages_sizes, height=OPTS.logic_buffers_height,
                             contact_pwell=True, contact_nwell=True,
                             route_outputs=False)
        self.add_mod(buffer)
        wire_length = max(self.driver_wire_length or 0.0,
                          3 * buffer.width)
        self.buffer_inst = self.add_inst("buffer", mod=buffer,
                                         offset=vector(0, 0))
        self.connect_inst(["in", "en", "en_bar", "vdd_buffer", "gnd"])
        self.copy_layout_pin(self.buffer_inst, "vdd", "vdd_buffer")
        self.copy_layout_pin(self.buffer_inst, "gnd", "gnd")
        self.copy_layout_pin(self.buffer_inst, "in", "in")

        # temporary add second buffer as load to
        # self.add_inst("temp_en_buf", mod=buffer.buffer_invs[0],
        #               offset=self.buffer_inst.ul() + vector(0, buffer.height))
        # self.connect_inst(["en_bar", "en_buf", "vdd", "gnd"])

        # Precharge Array
        x_offset = self.buffer_inst.rx() + wire_length
        self.precharge_array = PrechargeArray(precharge_size=self.precharge_size,
                                              num_elements=self.num_elements)
        self.add_mod(self.precharge_array)

        self.precharge_array_inst = self.add_inst("precharge_array",
                                                  mod=self.precharge_array,
                                                  offset=vector(x_offset, 0))
        terminals = []
        for i in range(self.num_elements):
            terminals.extend(["bl[{}]".format(i), "br[{}]".format(i)])
        terminals.extend(["en", "gnd", "vdd_precharge"])
        self.connect_inst(terminals)

        self.copy_layout_pin(self.precharge_array_inst, "vdd", "vdd_precharge")
        self.copy_layout_pin(self.precharge_array_inst, "gnd", "gnd")

        # connect buffer and precharge gnd, en
        buffer_names = ["gnd", "out_inv"]
        precharge_names = ["gnd", "en"]
        for i in range(2):
            buffer_pin = self.buffer_inst.get_pin(buffer_names[i])
            precharge_pin = self.precharge_array_inst.get_pin(precharge_names[i])
            if i == 0:
                height = buffer_pin.height()
            else:
                self.add_rect(METAL2, offset=precharge_pin.ul(),
                              height=buffer_pin.by() + self.m2_width - precharge_pin.uy())
                via_y = buffer_pin.by() + m1m2.width - m1m2.height
                self.add_contact(m1m2.layer_stack, offset=vector(precharge_pin.lx(),
                                                                 via_y))
                height = self.get_min_layer_width(buffer_pin.layer)
            self.add_rect(buffer_pin.layer, offset=buffer_pin.lr(),
                          width=precharge_pin.lx() - buffer_pin.rx() + 0.5 * self.m1_width,
                          height=height)

        # Bitcell array
        num_elements = self.num_elements
        num_bitcell_cols = num_elements if self.two_d else 1
        bitcell_arr = bitcell_array(cols=num_bitcell_cols, rows=num_elements)
        self.add_mod(bitcell_arr)
        self.bitcell_array = bitcell_arr
        # create space from precharge array
        precharge_bl = self.precharge_array_inst.get_pin(f"bl[{num_elements - 1}]")
        bitcell_bl = bitcell_arr.get_pin("bl[0]")
        x_offset = precharge_bl.lx() - bitcell_bl.lx()

        top_bitcell_y = bitcell.get_nwell_top()

        space = max(3 * self.implant_space, 3 * self.get_wide_space(NWELL))

        y_offset = (self.precharge_array_inst.uy() + (top_bitcell_y - bitcell.height) +
                    space)
        bitcell_array_inst = self.add_inst("bitcell_array", bitcell_arr,
                                           offset=vector(x_offset, y_offset))
        # terminals
        if self.two_d:
            terminals = []
            for col in range(num_elements):
                terminals.extend(["bl[{0}]".format(col), "br[{0}]".format(col)])
        else:
            terminals = ["bl[{}]".format(num_elements - 1), "br[{}]".format(num_elements - 1)]

        for i in range(num_elements):
            terminals.append("wl[{}]".format(i))
        terminals.extend(["vdd_bitcell", "gnd"])
        self.connect_inst(terminals)

        # connect lowest bitcell gnd with precharge gnd
        bitcell_gnds = bitcell_array_inst.get_pins("gnd")
        bottom_gnd = min(filter(lambda x: x.layer == METAL1, bitcell_gnds),
                         key=lambda x: x.by())
        precharge_gnd = self.precharge_array_inst.get_pin("gnd")
        extension = bitcell.width
        x_offset = precharge_gnd.rx() + extension
        self.add_rect(METAL1, offset=precharge_gnd.lr(), height=precharge_gnd.height(),
                      width=extension)
        self.add_rect(METAL1, offset=bottom_gnd.lr(), width=x_offset - bottom_gnd.rx(),
                      height=bottom_gnd.height())
        self.add_rect(METAL1, offset=vector(x_offset, precharge_gnd.by()),
                      width=precharge_gnd.height(),
                      height=bottom_gnd.uy() - precharge_gnd.by())

        # connect precharge and bitcell array bitlines
        for pin_name in ["bl", "br"]:
            for col in range(num_bitcell_cols):
                precharge_col = col if self.two_d else num_elements - 1
                bitcell_col = col if self.two_d else 0
                bitcell_pin = bitcell_array_inst.get_pin("{}[{}]".format(pin_name,
                                                                         bitcell_col))
                precharge_pin = self.precharge_array_inst.get_pin("{}[{}]".
                                                                  format(pin_name,
                                                                         precharge_col))
                self.add_rect(precharge_pin.layer, offset=precharge_pin.ul(),
                              width=precharge_pin.width(),
                              height=bitcell_pin.by() - precharge_pin.uy())

        self.copy_layout_pin(bitcell_array_inst, "vdd", "vdd_bitcell")
        self.copy_layout_pin(bitcell_array_inst, "gnd", "gnd")

        for i in range(num_elements):
            self.copy_layout_pin(bitcell_array_inst, "wl[{}]".format(i))
            self.copy_layout_pin(self.precharge_array_inst, "bl[{}]".format(i))
            self.copy_layout_pin(self.precharge_array_inst, "br[{}]".format(i))

    def add_pins(self):
        self.add_pin_list(["in", "vdd_precharge", "vdd_buffer",
                           "vdd_bitcell", "gnd"])
        for col in range(self.num_elements):
            self.add_pin_list(["bl[{0}]".format(col), "br[{0}]".format(col)])
        for row in range(self.num_elements):
            self.add_pin("wl[{}]".format(row))
