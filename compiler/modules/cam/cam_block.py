from bank_gate import ControlGate, BankGate
from collections import namedtuple
import contact
from modules import bank
import utils
from vector import vector


class CamBlock(bank.bank):
    """
    Generate a CAM block
    CAM banks are divided into blocks with word_size columns.
    word_size is loosely defined here. For example, it could be 64*n bits for a 64 bit system
    The blocks act independently with pin block_sel determining whether a block is activated
    pin block_sel should be the column decoder sel out`put
    """

    @staticmethod
    def get_module_list():
        sram_modules = bank.bank.get_module_list()
        cam_modules = ["address_mux_array", "sl_driver_array", "ml_precharge_array", "tag_flop_array"]
        return sram_modules + cam_modules

    def add_pins(self):
        for i in range(self.word_size):
            self.add_pin("DATA[{0}]".format(i))
        for i in range(self.word_size):
            self.add_pin("MASK[{0}]".format(i))
        for i in range(self.num_rows):
            self.add_pin("dec_out[{0}]".format(i))

        for pin in ["block_sel", "clk_buf", "s_en", "w_en", "search_en",
                    "matchline_chb", "mw_en", "sel_all", "latch_tags", "vdd", "gnd"]:
            self.add_pin(pin)


    def create_modules(self):
        super(CamBlock, self).create_modules()

        self.address_mux_array = self.mod_address_mux_array(rows=self.num_rows)
        self.add_mod(self.address_mux_array)

        self.sl_driver_array = self.mod_sl_driver_array(columns=self.num_cols, word_size=self.word_size)
        self.add_mod(self.sl_driver_array)

        self.ml_precharge_array = self.mod_ml_precharge_array(rows=self.num_rows, size=3)
        self.add_mod(self.ml_precharge_array)

        self.tag_flop_array = self.mod_tag_flop_array(rows=self.num_rows)
        self.add_mod(self.tag_flop_array)

    def create_column_decoder(self):
        """column decoders are created at the bank level if needed"""
        pass

    def create_bank_gate(self):
        control_gates = [

            # left
            ControlGate("s_en", [1, 4, 8], route_complement=True, output_dir="left"),
            ControlGate("search_en", [1, 2, 4], output_dir="left"),
            ControlGate("w_en", [1, 2, 4], output_dir="left"),
            ControlGate("latch_tags", [1, 2, 4], output_dir="left"),
            ControlGate("matchline_chb", [1, 2, 4], output_dir="left"),

            # right
            ControlGate("mw_en", [1, 2, 4], route_complement=True),
            ControlGate("sel_all", [2, 6, 8], route_complement=True),
            ControlGate("clk", [2, 6, 8], route_complement=True)  # to buffer the clk
        ]
        self.bank_gate = BankGate(control_gates, contact_nwell=True)
        self.input_control_signals = [ctrl_gate.signal_name for ctrl_gate in control_gates]
        self.add_mod(self.bank_gate)


    def add_modules(self):

        self.add_bitcell_array()
        self.add_precharge_array()

        self.add_sense_amp_array()
        self.add_sl_driver_array()
        self.add_write_driver_array()
        self.add_msf_mask_in()
        self.add_msf_data_in()
        self.add_tri_gate_array()
        self.add_bank_gate()

        self.add_ml_precharge_array()
        self.add_tag_flops()

        self.add_wordline_driver()
        self.add_address_mux_array()

        self.msf_address_inst = None
        self.column_decoder_inst = None

    def route_layout(self):
        self.route_precharge_to_bitcell_array()
        self.route_sense_amp_to_trigate()
        self.route_bank_sel()
        self.route_tri_gate_out()
        self.route_mask_in()
        self.route_write_driver_inputs()
        self.route_write_driver_bitlines()
        self.route_sl_driver_searchlines()
        self.route_right_controls()
        self.route_left_controls()
        self.route_wordline_driver()
        self.route_tag_flops()

        self.calculate_rail_vias()
        self.route_vdd_supply()
        self.route_gnd_supply()

    def route_sense_amp_to_trigate(self):
        """ Routing of sense amp output to tri_gate input """

        self.bend_x = min(utils.ceil(0.4 * self.bitcell.width), 4*self.m3_width)

        for i in range(self.word_size):
            sa_data_out = self.sense_amp_array_inst.get_pin("data[{}]".format(i))
            tri_gate_in = self.tri_gate_array_inst.get_pin("in[{}]".format(i))

            # go down to middle of data flop
            flop_y = 0.5*(self.msf_mask_in_inst.by() + self.msf_mask_in_inst.uy())

            self.add_rect("metal3", offset=vector(sa_data_out.lx(), flop_y), width=sa_data_out.width(),
                          height=sa_data_out.by() - flop_y)

            # go left to avoid data in pins of the flip flop arrays
            x_offset = sa_data_out.lx() - self.bend_x
            self.add_rect("metal3", offset=vector(x_offset, flop_y), width=self.bend_x)

            # go down to just above tri gate input pin

            self.add_rect("metal3", offset=vector(x_offset, tri_gate_in.by()), height=flop_y - tri_gate_in.by())

            self.add_rect("metal2", offset=vector(x_offset, tri_gate_in.by()), width=tri_gate_in.rx() - x_offset)

            self.add_contact(contact.m2m3.layer_stack, offset=vector(x_offset, tri_gate_in.by()))

    def route_bank_sel(self):
        # add input pins
        m1_extension = 0.5 * contact.m1m2.second_layer_height + self.line_end_space  # space to prevent via clash
        stagger = True
        for pin_name in ["bank_sel"] + self.input_control_signals:
            pin = self.bank_gate_inst.get_pin(pin_name)
            if pin_name == "clk":
                layout_name = "clk_buf"
            elif pin_name == "bank_sel":
                layout_name = "block_sel"
            else:
                layout_name = pin_name
            if pin.layer == "metal1":
                if stagger:
                    self.add_rect("metal1", offset=pin.lr(), width=m1_extension)
                    via_x = pin.rx() + m1_extension + contact.m1m2.second_layer_height
                    stagger = False
                else:
                    via_x = pin.rx() + contact.m1m2.second_layer_height
                    stagger = True

                self.add_contact(layers=contact.m1m2.layer_stack, offset=vector(via_x, pin.by()), rotate=90)
                self.add_layout_pin(layout_name, "metal2", offset=vector(via_x, pin.by()), width=self.right_edge - via_x)
            else:
                self.add_layout_pin(layout_name, "metal2", offset=pin.lr(), width=self.right_edge - pin.rx())

    def route_tri_gate_out(self):
        super(CamBlock, self).route_tri_gate_out()
        for i in range(self.word_size):
            tri_gate_out = self.tri_gate_array_inst.get_pin("out[{}]".format(i))
            self.add_contact(contact.m2m3.layer_stack,
                             offset=tri_gate_out.ul() - vector(0, contact.m2m3.second_layer_height))

    def route_mask_in(self):
        """ Metal 3 routing of mask in """
        data_in_midpoint = 0.5 * (self.msf_data_in_inst.by() + self.msf_data_in_inst.uy())
        for i in range(self.word_size):
            mask_in_flop = self.msf_mask_in_inst.get_pin("din[{0}]".format(i))
            x_offset = mask_in_flop.rx() + self.bend_x

            self.add_layout_pin(text="MASK[{}]".format(i), layer="metal3",
                                offset=vector(x_offset, self.min_point),
                                height=data_in_midpoint - self.min_point)

            # create bend to middle
            self.add_rect("metal3", offset=vector(mask_in_flop.lx(), data_in_midpoint),
                          width=x_offset - mask_in_flop.lx() + self.m3_width)
            self.add_rect("metal3", offset=vector(mask_in_flop.lx(), data_in_midpoint),
                          height=mask_in_flop.by() - data_in_midpoint)
            self.add_contact(contact.m2m3.layer_stack, offset=mask_in_flop.ll())

    def route_write_driver_inputs(self):
        """Connect data flip flop outputs to write driver data pin and mask flip flop outputs to write driver mask pin"""

        for i in range(self.word_size):
            # route mask
            mask_flop_out = self.msf_mask_in_inst.get_pin("dout[{0}]".format(i))
            writer_mask_in = filter(lambda pin: pin.layer == "metal3",
                                    self.write_driver_array_inst.get_pins("mask[{}]".format(i)))[0]
            self.add_rect("metal2", offset=vector(writer_mask_in.lx(), mask_flop_out.uy() - self.m2_width),
                          width=mask_flop_out.lx() - writer_mask_in.lx())
            self.add_contact(contact.m2m3.layer_stack,
                             offset=vector(writer_mask_in.lx(), mask_flop_out.uy() - contact.m2m3.second_layer_height))
            self.add_rect("metal3", offset=vector(writer_mask_in.lx(), mask_flop_out.uy()),
                          height=writer_mask_in.by() - mask_flop_out.uy())

            # route data
            mask_in_midpoint = 0.5 * (self.msf_mask_in_inst.by() + self.msf_mask_in_inst.uy())
            data_flop_out = self.msf_data_in_inst.get_pin("dout[{0}]".format(i))
            data_flop_out_bar = self.msf_data_in_inst.get_pin("dout_bar[{0}]".format(i))
            writer_data_in = self.write_driver_array_inst.get_pin("data[{}]".format(i))

            x_offset = 0.5*(data_flop_out_bar.cx() + data_flop_out.cx() - self.m3_width)
            if x_offset > writer_data_in.lx():
                x_offset = writer_data_in.lx()

            self.add_rect("metal2", offset=data_flop_out.ul() - vector(0, self.m2_width),
                          width=x_offset - data_flop_out.lx())
            self.add_contact(contact.m2m3.layer_stack, offset=vector(x_offset, data_flop_out.uy() - self.m2_width))
            self.add_rect("metal3", offset=vector(x_offset, data_flop_out.uy()),
                          height=mask_in_midpoint - data_flop_out.uy())
            self.add_rect("metal3", offset=vector(x_offset, mask_in_midpoint), width=writer_data_in.lx() - x_offset)
            self.add_rect("metal3", offset=vector(writer_data_in.lx(), mask_in_midpoint),
                          height=writer_data_in.by() - mask_in_midpoint)
            self.add_contact(contact.m3m4.layer_stack, offset=writer_data_in.ll())

    def route_write_driver_bitlines(self):
        """Connect metal4 bitlines from write driver to bottom of sense amp """
        pin_names = ["bl[{}]", "br[{}]"]
        for i in range(self.word_size):
            for pin_name in pin_names:
                driver_out_pin = self.write_driver_array_inst.get_pin(pin_name.format(i))
                sense_amp_pin = self.sense_amp_array_inst.get_pin(pin_name.format(i))
                self.add_rect("metal4", offset=driver_out_pin.ul(), height=sense_amp_pin.by() - driver_out_pin.uy())

    def route_sl_driver_searchlines(self):
        pin_names = ["sl[{}]", "slb[{}]"]
        for i in range(self.word_size):
            for pin_name in pin_names:
                driver_out_pin = self.sl_driver_array_inst.get_pin(pin_name.format(i))
                bitcell_in_pin = self.bitcell_array_inst.get_pin(pin_name.format(i))
                self.add_rect("metal4", vector(bitcell_in_pin.lx(), driver_out_pin.uy()),
                              height=bitcell_in_pin.by() - driver_out_pin.uy())

    def route_right_controls(self):
        """Create right side rails below the matchline precharge and tag flops.
        """

        Rail = namedtuple("Rail", ["gate_pin", "dest_pin", "direction"])

        rails = [
            Rail(self.prefix + "matchline_chb", self.ml_precharge_array_inst.get_pin("precharge_bar"), "up"),
            Rail(self.prefix + "latch_tags", self.tag_flop_array_inst.get_pin("clk"), "up"),
            Rail(self.prefix + "w_en", self.write_driver_array_inst.get_pin("en"), "left"),
            Rail(self.prefix + "search_en", self.sl_driver_array_inst.get_pin("en"), "left"),
            Rail(self.prefix + "s_en", self.sense_amp_array_inst.get_pin("en"), "left")
            ]
        x_offset = self.ml_precharge_array_inst.get_pin("precharge_bar").lx() + self.line_end_space
        for rail in rails:
            self.rail_lines[rail.gate_pin] = x_offset
            gate_pin = self.bank_gate_inst.get_pin(rail.gate_pin)
            dest_pin = rail.dest_pin
            self.add_rect("metal2", offset=gate_pin.lr(), width=x_offset + self.m2_width - gate_pin.rx())
            self.add_rect("metal2", offset=vector(x_offset, gate_pin.by() + self.m2_width),
                          height=dest_pin.by() - gate_pin.by())

            if rail.direction == "up":
                if dest_pin.lx() == x_offset:
                    pass
                elif dest_pin.lx() < x_offset:
                    self.add_rect("metal2", offset=dest_pin.ll(), width=x_offset - dest_pin.lx())
                else:
                    self.add_rect("metal2", offset=vector(x_offset, dest_pin.by()), width=dest_pin.rx() - x_offset)
            elif rail.direction == "left":
                via_x = dest_pin.rx() + self.line_end_space
                if rail.gate_pin == self.prefix + "w_en": # move away from ground pin
                    via_y = dest_pin.uy() + self.line_end_space + 0.5 * contact.m1m2.second_layer_height
                    self.add_rect("metal2", offset=vector(via_x, dest_pin.by()), height=via_y - dest_pin.by())
                    self.add_rect("metal2", offset=vector(x_offset, dest_pin.by()), height=via_y - dest_pin.by())
                else:
                    via_y = dest_pin.cy() - 0.5*contact.m1m2.second_layer_height
                self.add_contact(contact.m1m2.layer_stack, offset=vector(x_offset, via_y))
                if dest_pin.layer == "metal1":
                    self.add_rect("metal1", offset=vector(dest_pin.rx(), dest_pin.by()), width=x_offset - dest_pin.rx())
                else:
                    self.add_rect("metal1",
                                  offset=vector(via_x, via_y + 0.5*(contact.m1m2.second_layer_height - self.m1_width)),
                                  width=x_offset - via_x)
                    self.add_rect("metal2", offset=dest_pin.lr(), width=via_x - dest_pin.rx())
                    self.add_contact(contact.m1m2.layer_stack, offset=vector(via_x, via_y))

            x_offset += self.m2_pitch

        # connect tri gates, assumes pins are connected all the way to the right edge
        # tri en
        x_offset = self.rail_lines[self.prefix + "s_en"]
        dest_pin = self.tri_gate_array_inst.get_pin("en")
        via_y = dest_pin.cy() - 0.5 * contact.m1m2.second_layer_height
        via_x = self.tri_gate_array_inst.rx() + self.line_end_space
        self.add_contact(contact.m1m2.layer_stack, offset=vector(x_offset, via_y))
        self.add_rect("metal1", offset=vector(via_x, dest_pin.by()), width=x_offset - via_x)
        self.add_rect("metal2", offset=vector(self.tri_gate_array_inst.rx(), dest_pin.by()),
                      width=via_x - self.tri_gate_array_inst.rx())
        self.add_contact(contact.m1m2.layer_stack, offset=vector(via_x, via_y))

        # tri_en_bar
        x_offset += self.m2_pitch
        pin_name = self.prefix + "s_en_bar"
        self.rail_lines[pin_name] = x_offset
        gate_pin = self.bank_gate_inst.get_pin(pin_name)
        dest_pin = self.tri_gate_array_inst.get_pin("en_bar")
        via_y = dest_pin.cy() - 0.5 * contact.m1m2.second_layer_height
        self.add_rect("metal2", offset=gate_pin.lr(), width=x_offset + self.m2_width - gate_pin.rx())
        self.add_rect("metal2", offset=vector(x_offset, gate_pin.by() + self.m2_width),
                      height=dest_pin.by() - gate_pin.by())
        self.add_contact(contact.m1m2.layer_stack, offset=vector(x_offset, via_y))
        self.add_rect("metal1", offset=vector(via_x, dest_pin.by()), width=x_offset - via_x)
        self.add_rect("metal2", offset=vector(self.tri_gate_array_inst.rx(), dest_pin.by()),
                      width=via_x - self.tri_gate_array_inst.rx())
        self.add_contact(contact.m1m2.layer_stack, offset=vector(via_x, via_y))




    def route_left_controls(self):
        """ Route the control lines for address mux and wordline driver, flip flops and precharge """

        Rail = namedtuple("Rail", ["gate_pin", "dest_pin"])

        # address mux and wordline driver

        rails = [
            Rail(self.prefix + "clk", self.wordline_driver_inst.get_pin("en")),
            Rail(self.prefix + "mw_en", self.address_mux_array_inst.get_pin("sel")),
            Rail(self.prefix + "mw_en_bar", self.address_mux_array_inst.get_pin("sel_bar")),
            Rail(self.prefix + "sel_all", self.address_mux_array_inst.get_pin("sel_all")),
            Rail(self.prefix + "sel_all_bar", self.address_mux_array_inst.get_pin("sel_all_bar"))
        ]
        for rail in rails:
            dest_pin = rail.dest_pin
            gate_pin = self.bank_gate_inst.get_pin(rail.gate_pin)
            self.rail_lines[rail.gate_pin] = dest_pin.lx()
            offset = vector(dest_pin.lx(), gate_pin.by())
            self.add_rect("metal1", offset=offset, width=gate_pin.lx() - dest_pin.lx())
            self.add_rect("metal2", offset=offset, height=dest_pin.by() - gate_pin.by())
            self.add_contact(contact.m1m2.layer_stack, offset=offset)

        # mask, data flops and precharge en
        Rail = namedtuple("Rail", ["gate_pin", "dest_pin", "rail_index"])
        rails = [
            Rail(self.prefix + "clk_bar", self.msf_data_in_inst.get_pin("clk"), 0),
            Rail(self.prefix + "clk_bar", self.precharge_array_inst.get_pin("en"), 0),
            Rail(self.prefix + "clk", self.msf_mask_in_inst.get_pin("clk"), 1),
        ]
        for rail in rails:
            x_offset = self.start_of_central_bus + rail.rail_index * self.m2_pitch
            dest_pin = rail.dest_pin
            gate_pin = self.bank_gate_inst.get_pin(rail.gate_pin)
            offset = vector(x_offset, gate_pin.by())
            self.add_rect("metal1", offset=offset, width=gate_pin.lx() - x_offset)
            self.add_rect("metal2", offset=offset, height=dest_pin.uy() - gate_pin.by())
            self.add_contact(contact.m1m2.layer_stack, offset=offset + vector(contact.m1m2.second_layer_height, 0),
                             rotate=90)
            self.add_contact(contact.m1m2.layer_stack, offset=vector(x_offset, dest_pin.by()))
            self.add_rect("metal1", offset=vector(x_offset, dest_pin.by()), width=dest_pin.lx() - x_offset)

    def route_wordline_driver(self):
        """ Connecting Wordline driver output to Bitcell WL connection  """

        # we don't care about bends after connecting to the input pin, so let the path code decide.
        for i in range(self.num_rows):
            # The pre/post is to access the pin from "outside" the cell to avoid DRCs
            address_mux_pin = self.address_mux_array_inst.get_pin("out[{}]".format(i))
            driver_in_pin = self.wordline_driver_inst.get_pin("in[{}]".format(i))

            if address_mux_pin.by() < driver_in_pin.by():
                self.add_rect("metal1", offset=address_mux_pin.lr(), height=driver_in_pin.uy() - address_mux_pin.by())
            else:
                self.add_rect("metal1", offset=vector(address_mux_pin.rx(), driver_in_pin.by()),
                              height=address_mux_pin.uy() - driver_in_pin.by())

            # The mid guarantees we exit the input cell to the right.
            driver_wl_pos = self.wordline_driver_inst.get_pin("wl[{}]".format(i)).rc()
            bitcell_wl_pos = self.bitcell_array_inst.get_pin("wl[{}]".format(i)).lc()
            self.add_path("metal1", [vector(driver_wl_pos.x, bitcell_wl_pos.y), bitcell_wl_pos])

        # route the gnd rails, add contact to rail as well
        for gnd_pin in self.wordline_driver_inst.get_pins("gnd"):
            self.route_gnd_from_left(gnd_pin)
            self.add_rect("metal1", offset=gnd_pin.lr(), height=gnd_pin.height(),
                          width=self.gnd_x_offset - gnd_pin.rx())

        # route the vdd rails
        for vdd_pin in self.wordline_driver_inst.get_pins("vdd"):
            self.add_rect("metal1", height=vdd_pin.height(),
                          offset=vector(vdd_pin.rx(), vdd_pin.by()),
                          width=self.bitcell_array_inst.lx() - vdd_pin.rx())

    def route_tag_flops(self):
        for row in range(self.num_rows):
            flop_pin = self.tag_flop_array_inst.get_pin("dout[{}]".format(row))
            mux_pin = self.address_mux_array_inst.get_pin("tag[{}]".format(row))
            # avoid flip flop obstruction. Note this is flip flop layout dependent
            if row % 2 == 0:
                y_shift = self.line_end_space
            else:
                y_shift = -self.line_end_space
            bend_x = self.tag_flop_array_inst.lx() - self.line_end_space
            self.add_path("metal3", [flop_pin.center(),
                                     vector(flop_pin.cx(), mux_pin.cy() + y_shift),
                                     vector(bend_x, mux_pin.cy() + y_shift),
                                     vector(bend_x, mux_pin.cy()),
                                     mux_pin.rc()])

    def get_collisions(self):
        """Get potential collisions with power routing grid"""
        collisions = []
        for row in range(self.num_rows):
            mux_pin = self.address_mux_array_inst.get_pin("tag[{}]".format(row))
            collisions.append((mux_pin.by(), mux_pin.uy()))
        control_pins = sorted(map(self.bank_gate_inst.get_pin, self.input_control_signals + ["bank_sel"]), key=lambda x: x.by())
        collisions.append((control_pins[0].by(), control_pins[-1].uy()))
        return collisions

    def route_vdd_supply(self):
        self.vdd_grid_vias = self.power_grid_vias[1::2]
        self.vdd_grid_rects = []

        offset = vector(self.right_vdd_x_offset, self.min_point)
        self.add_layout_pin(text="vdd",
                            layer="metal1",
                            offset=offset,
                            width=self.vdd_rail_width,
                            height=self.height)
        m9_x_offset = self.right_vdd_x_offset + self.vdd_rail_width-self.m1mtop.second_layer_width
        self.add_layout_pin("vdd",
                            layer=self.top_power_layer,
                            offset=vector(m9_x_offset, self.min_point),
                            width=self.grid_rail_width,
                            height=self.height)
        for via_y in self.vdd_grid_vias:
            self.add_inst(self.m1mtop.name, self.m1mtop,
                          offset=vector(self.right_vdd_x_offset + self.vdd_rail_width, via_y),
                          mirror="MY")
            self.connect_inst([])

        for inst in [self.precharge_array_inst, self.sense_amp_array_inst, self.sl_driver_array_inst,
                     self.write_driver_array_inst, self.msf_data_in_inst, self.msf_mask_in_inst, self.tag_flop_array_inst,
                     self.tri_gate_array_inst, self.bank_gate_inst, self.bitcell_array_inst]:
            if inst is None:
                continue
            for vdd_pin in inst.get_pins("vdd"):
                self.add_rect(layer="metal1",
                              offset=vdd_pin.lr(),
                              width=self.right_vdd_x_offset - vdd_pin.rx(),
                              height=vdd_pin.height())

    def route_gnd_supply(self):
        # add vertical rail

        offset = vector(self.gnd_x_offset, self.min_point)
        self.add_layout_pin(text="gnd",
                            layer="metal2",
                            offset=offset,
                            width=self.gnd_rail_width,
                            height=self.height)
        # add grid
        self.gnd_grid_vias = self.power_grid_vias[0::2]
        self.gnd_grid_rects = []
        rect_x_offset = self.gnd_x_offset + 0.5 * (self.gnd_rail_width - self.grid_rail_width)
        self.add_layout_pin("gnd", self.top_power_layer,
                            offset=vector(rect_x_offset, self.min_point),
                            width=self.grid_rail_width,
                            height=self.height)
        via_x_offset = self.gnd_x_offset + 0.5 * self.gnd_rail_width
        for via_y in self.gnd_grid_vias:
            self.gnd_grid_rects.append(self.add_inst(self.m2mtop.name, self.m2mtop,
                                                     offset=vector(via_x_offset, via_y)))
            self.connect_inst([])

        # make dummy contact for measurements
        layers = ("metal1", "via1", "metal2")
        contact_size = [2, 1]
        dummy_contact = contact.contact(layer_stack=layers, dimensions=contact_size)
        contact_width = dummy_contact.first_layer_width + dummy_contact.first_layer_vertical_enclosure

        for inst in [self.sense_amp_array_inst, self.sl_driver_array_inst, self.bitcell_array_inst,
                     self.write_driver_array_inst, self.msf_data_in_inst, self.msf_mask_in_inst,
                     self.tri_gate_array_inst, self.bank_gate_inst]:
            if inst is None:
                continue
            for gnd_pin in inst.get_pins("gnd"):
                pin_pos = gnd_pin.ll()
                gnd_offset = vector(self.gnd_x_offset + self.gnd_rail_width - contact_width, pin_pos.y)
                self.add_rect("metal1", gnd_offset, width=pin_pos.x - gnd_offset.x, height=gnd_pin.height())
                self.add_via(layers=layers,
                             offset=gnd_offset,
                             size=contact_size,
                             rotate=0)


    def compute_sizes(self):
        super(CamBlock, self).compute_sizes()

        self.control_signals = map(lambda x: self.prefix + x,
                                   ["s_en", "clk_bar", "clk_buf", "tri_en_bar", "tri_en", "w_en"])

        self.num_left_rails = 2  # clk and clk_bar

        self.start_of_central_bus = -(self.num_left_rails * self.m2_pitch + self.parallel_line_space)
        # one pitch on the right on the addr lines and one on the right of the gnd rail

        self.gnd_x_offset = self.start_of_central_bus - self.gnd_rail_width - self.m2_pitch

        # add a pitch on each end and around the gnd rail
        self.overall_central_bus_width = -self.gnd_x_offset + self.parallel_line_space

        self.rail_lines = {}



    def get_sense_amp_offset(self):
        return vector(0, -self.sense_amp_array.height)

    def get_tri_gate_offset(self):
        return self.msf_data_in_inst.by()

    def compute_width(self):
        self.right_vdd_x_offset = self.tag_flop_array_inst.rx() + 1.5*self.wide_m1_space
        self.right_edge = self.right_vdd_x_offset + self.vdd_rail_width
        self.left_edge = self.address_mux_array_inst.lx()
        self.width = self.right_edge - self.left_edge

    def add_bitcell_array(self):
        """ Adding Bitcell Array """

        self.bitcell_array_inst=self.add_inst(name="bitcell_array",
                                              mod=self.bitcell_array,
                                              offset=vector(0,0))
        temp = []
        for i in range(self.num_cols):
            temp.append("bl[{0}]".format(i))
            temp.append("br[{0}]".format(i))
            temp.append("sl[{0}]".format(i))
            temp.append("slb[{0}]".format(i))
        for j in range(self.num_rows):
            temp.append("wl[{0}]".format(j))
            temp.append("ml[{0}]".format(j))
        temp.extend(["vdd", "gnd"])
        self.connect_inst(temp)

    def add_write_driver_array(self):
        """ Adding Write Driver  """

        y_offset = self.sl_driver_array_inst.by() - self.write_driver_array.height
        self.write_driver_array_inst = self.add_inst(name="write_driver_array",
                                                     mod=self.write_driver_array,
                                                     offset=vector(0, y_offset))

        temp = []
        for i in range(self.word_size):
            temp.append("data_in[{0}]".format(i))
        for i in range(self.word_size):
            if (self.words_per_row == 1):
                temp.append("bl[{0}]".format(i))
                temp.append("br[{0}]".format(i))
            else:
                temp.append("bl_out[{0}]".format(i))
                temp.append("br_out[{0}]".format(i))
        for i in range(self.word_size):
            temp.append("mask_in[{}]".format(i))
        temp.extend([self.prefix + "w_en", "vdd", "gnd"])
        self.connect_inst(temp)

    def add_sl_driver_array(self):
        offset = self.sense_amp_array_offset + vector(0, -self.sl_driver_array.height)
        self.sl_driver_array_inst = self.add_inst(name="sl_driver_array", mod=self.sl_driver_array, offset=offset)

        temp = []
        for i in range(self.num_cols):
            temp.append("data_in[{0}]".format(i))
            temp.append("sl[{0}]".format(i))
            temp.append("slb[{0}]".format(i))
            temp.append("mask_in[{0}]".format(i))
        temp.append(self.prefix + "search_en")
        temp.append("vdd")
        temp.append("gnd")

        self.connect_inst(temp)

    def get_msf_data_in_y_offset(self):
        y_space = self.parallel_line_space
        return self.msf_mask_in_inst.by() - self.msf_data_in.height - y_space


    def add_msf_mask_in(self):
        """ mask in flip flop"""

        offset = self.write_driver_array_inst.ll() - vector(0, self.msf_data_in.height)

        self.msf_mask_in_inst = self.add_inst(name="mask_in_flop_array",
                                              mod=self.msf_data_in,
                                              offset=offset)
        temp = []
        for i in range(self.word_size):
            temp.append("MASK[{0}]".format(i))
        for i in range(self.word_size):
            temp.append("mask_in[{0}]".format(i))
            temp.append("mask_in_bar[{0}]".format(i))
        temp.extend([self.prefix + "clk_buf", "vdd", "gnd"])
        self.connect_inst(temp)

    def add_bank_gate(self):
        """Add bank gate instance"""
        tri_gate_vdd = self.tri_gate_array_inst.get_pin("vdd")

        x_offset = max(0, 0.5 * self.bitcell_array_inst.rx() - 0.5 * self.bank_gate.width) + self.bank_gate.width

        y_space = 0.5*tri_gate_vdd.height() + self.line_end_space

        y_offset = self.tri_gate_array_inst.by() - self.bank_gate.height - y_space

        self.bank_gate_inst = self.add_inst(name="bank_gate", mod=self.bank_gate,
                                            offset=vector(x_offset, y_offset),
                                            mirror="MY")
        temp = (["block_sel", "s_en", "search_en", "w_en", "latch_tags", "matchline_chb", "mw_en", "sel_all", "clk_buf"]
                + [self.prefix + x for x in ["s_en_bar", "s_en", "search_en", "w_en", "latch_tags", "matchline_chb",
                                             "mw_en_bar", "mw_en", "sel_all_bar", "sel_all", "clk_bar", "clk_buf"]] +
                ["vdd", "gnd"])

        self.connect_inst(temp)

    def add_ml_precharge_array(self):
        self.ml_precharge_array_inst = self.add_inst(name="ml_precharge_array", mod=self.ml_precharge_array,
                                                     offset=vector(self.bitcell_array_inst.rx(), 0))
        # fill pimplant below bitcell precharge array
        y_offset = self.bitcell_array_inst.uy()
        fill_height = self.precharge_array_inst.by() - y_offset
        self.add_rect("pimplant", offset=vector(self.bitcell_array_inst.rx(), y_offset),
                      width=0.5 * self.ml_precharge_array.width, height=fill_height)
        temp = []
        temp.append(self.prefix + "matchline_chb")
        for i in range(self.num_rows):
            temp.append("ml[{0}]".format(i))
        temp.append("vdd")
        self.connect_inst(temp)

    def add_tag_flops(self):
        self.tag_flop_array_inst = self.add_inst(name="tag_flop_array", mod=self.tag_flop_array,
                                                 offset=self.ml_precharge_array_inst.lr())
        temp = []
        for i in range(self.num_rows):
            temp.append("ml[{0}]".format(i))
        for i in range(self.num_rows):
            temp.append("tag[{0}]".format(i))
            temp.append("tag_bar[{0}]".format(i))
        temp.append(self.prefix + "latch_tags")
        temp.append("vdd")
        temp.append("gnd")
        self.connect_inst(temp)


    def add_wordline_driver(self):
        self.wordline_x_offset = -self.overall_central_bus_width - self.wordline_driver.width
        super(CamBlock, self).add_wordline_driver()

    def add_address_mux_array(self):
        offset = self.wordline_driver_inst.ll() - vector(self.address_mux_array.width, 0)
        self.address_mux_array_inst = self.add_inst(name="address_mux_array", mod=self.address_mux_array, offset=offset)

        temp = []

        for i in range(self.num_rows):
            temp.append("dec_out[{0}]".format(i))
            temp.append("tag[{0}]".format(i))
            temp.append("wl_in[{0}]".format(i))
        temp.append(self.prefix + "mw_en")
        temp.append(self.prefix + "mw_en_bar")
        temp.append(self.prefix + "sel_all")
        temp.append(self.prefix + "sel_all_bar")
        temp.append("vdd")
        temp.append("gnd")

        self.connect_inst(temp)
        for row in range(self.num_rows):
            self.copy_layout_pin(self.address_mux_array_inst, "dec[{}]".format(row), "dec_out[{0}]".format(row))

    def connect_inst(self, args, check=True):
        instance = self.insts[-1]
        if instance.name == "wordline_driver":
            args = self.replace_args("dec_out", "wl_in", args)
        elif instance.name == "tri_gate_array":
            args = self.replace_args(self.prefix + "tri_en", self.prefix + "s_en", args)
            args = self.replace_args(self.prefix + "tri_en_bar", self.prefix + "s_en_bar", args)

        super(CamBlock, self).connect_inst(args, check)

    def replace_args(self, from_name, to_name, args):
        args = [arg.replace(from_name, to_name) for arg in args]
        return args






