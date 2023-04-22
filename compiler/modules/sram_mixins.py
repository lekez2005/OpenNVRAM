import datetime
import os
from typing import TYPE_CHECKING

import debug
from base import utils
from base.contact import m2m3, m1m2, cross_m2m3, m3m4
from base.design import METAL3, METAL2, METAL4
from base.layout_clearances import find_clearances, VERTICAL
from base.vector import vector
from globals import OPTS, print_time
from modules.horizontal.pinv_wordline import pinv_wordline

if TYPE_CHECKING:
    from modules.baseline_sram import BaselineSram
else:
    class BaselineSram:
        pass


class DecoderAddressPins(BaselineSram):
    def calculate_row_decoder_col_decoder_y_space(self):
        from modules.baseline_sram import BaselineSram
        space = BaselineSram.calculate_row_decoder_col_decoder_y_space(self)
        bottom_address_pins = self.row_decoder.all_predecoders[0].number_of_inputs
        return space + bottom_address_pins * self.bus_pitch

    def add_address_pins(self):
        debug.info(1, "Route address pins")

        current_y_base = self.bank_inst.uy()
        pin_count = 0
        pin_space = 0.5 * self.rail_height + self.m3_space + self.bus_pitch

        pitch = self.address_pin_pitch

        x_offset = self.leftmost_m2_rail_x - 2 * self.bus_pitch - self.m4_width

        # avoid m2 rails
        obstruction_pins = [self.bank_inst.get_pin(x) for x in self.bank_flop_inputs]
        obstruction_span = [min(map(lambda x: x.lx(), obstruction_pins)),
                            max(map(lambda x: x.rx(), obstruction_pins))]
        obstruction_span = [obstruction_span[0] - pitch, obstruction_span[1] + m3m4.h_2]

        def get_open_x(x_offset_):
            if obstruction_span[0] <= x_offset_ <= obstruction_span[1]:
                return obstruction_span[0]
            return x_offset_

        # avoid m3 rails
        top_address_pin = self.row_decoder_inst.get_pin(f"a[{self.row_addr_size - 1}]")
        open_y_spaces = find_clearances(self, METAL3, direction=VERTICAL,
                                        recursive=False,
                                        region=(self.row_decoder_inst.rx(), self.leftmost_m2_rail_x),
                                        existing=[(self.min_point, top_address_pin.by())])
        open_y_spaces = list(reversed(open_y_spaces))

        def get_open_y(y_offset_):
            while True:
                has_obstruction = True
                for bottom, top in open_y_spaces:
                    if bottom + self.bus_space <= y_offset_ <= top - self.bus_pitch:
                        has_obstruction = False
                        break
                if not has_obstruction:
                    return y_offset_
                y_offset_ -= self.bus_space

        y_offset = top_address_pin.by()

        pin_order = (list(range(self.col_addr_size, self.row_addr_size + self.col_addr_size)) +
                     list(reversed(range(self.col_addr_size))))

        for index, bit in enumerate(pin_order):

            target_net = f"ADDR[{bit}]"
            conn_index = [index for index, conn in enumerate(self.conns) if target_net in conn][0]
            pin_index = self.conns[conn_index].index(target_net)
            decoder_inst = self.insts[conn_index]
            existing_pin = decoder_inst.get_pin(decoder_inst.mod.pins[pin_index])

            is_flop = self.col_addr_size == 1 and bit == 0

            m3_rail_x = existing_pin.cx()

            if target_net.lower() in self.pin_map:
                self.pin_map.pop(target_net.lower())

            if not is_flop:
                bottom_y = utils.round_to_grid(existing_pin.by())
                if not bottom_y == current_y_base:
                    current_y_base = bottom_y
                    pin_count = 0
                    y_offset = bottom_y - pin_space
                else:
                    y_offset = y_offset - self.bus_pitch
            else:
                via_offset = existing_pin.lc() - vector(0.5 * m2m3.h_1, 0)
                m3_rail_x = via_offset.x
                self.add_contact_center(m2m3.layer_stack, via_offset, rotate=90)
                x_offset = min(x_offset, via_offset.x - m2m3.h_1)

                y_offset = min(y_offset - self.bus_pitch, existing_pin.cy() - 0.5 * self.bus_width)

            y_offset = get_open_y(y_offset)
            x_offset = get_open_x(x_offset)

            mid_x = x_offset + 0.5 * self.m4_width
            via_y = y_offset + 0.5 * self.bus_width
            if not is_flop:
                self.add_rect(METAL2, vector(existing_pin.lx(), y_offset),
                              width=existing_pin.width(), height=existing_pin.by() - y_offset)

                self.add_cross_contact_center(m2m3, vector(existing_pin.cx(), via_y), fill=False)
            m3_height = m3m4.w_1
            self.add_rect(METAL3, vector(x_offset, via_y - 0.5 * m3_height),
                          height=m3_height, width=m3_rail_x - x_offset)

            self.add_cross_contact_center(m3m4, vector(mid_x, via_y),
                                          fill=False, rotate=True)
            self.add_layout_pin(target_net, METAL4, vector(x_offset, self.min_point),
                                height=via_y - self.min_point)

            x_offset -= pitch
            pin_count += 1


class StackedDecoderMixin(BaselineSram):
    def get_decoder_output_offsets(self, bank_inst):
        offsets = []
        for row in range(self.bank.num_rows):
            wordline_in = bank_inst.get_pin("dec_out[{}]".format(row))
            y_offset = wordline_in.by()
            if row % 2 == 0:
                decoder_out = self.row_decoder_inst.get_pin("decode[{}]".format(row))
                is_stacked = decoder_out.cx() < self.row_decoder_inst.cx()
                if is_stacked:
                    y_offset = decoder_out.by() - 0.5 * m2m3.h_2 - 0.5 * self.m3_width
            offsets.append(y_offset)
        return offsets

    def route_decoder_outputs(self):
        for i in range(len(self.bank_insts)):
            bank_inst = self.bank_insts[i]
            y_offsets = self.get_decoder_output_offsets(bank_inst)
            for row in range(self.bank.num_rows):
                decoder_out = self.row_decoder_inst.get_pin("decode[{}]".format(row))
                rail_offset = y_offsets[row]
                wordline_in = bank_inst.get_pin("dec_out[{}]".format(row))
                if row % 2 == 0:
                    self.add_rect(METAL2, offset=decoder_out.ll(),
                                  height=rail_offset - decoder_out.by())
                else:
                    self.add_rect(METAL2, offset=decoder_out.ul(),
                                  height=rail_offset - decoder_out.uy())
                via_shift = 0.5 * m1m2.w_2 - 0.5 * m2m3.w_1
                if decoder_out.cx() > self.row_decoder_inst.cx():
                    via_x = decoder_out.cx() - via_shift
                else:
                    via_x = decoder_out.cx() + via_shift
                via_offset = vector(via_x, rail_offset + 0.5 * self.m3_width)

                if isinstance(self.row_decoder.inv, pinv_wordline):
                    self.add_contact_center(m1m2.layer_stack, offset=via_offset)
                self.add_cross_contact_center(cross_m2m3, offset=via_offset, fill=False)
                if i == 0:
                    end_x = wordline_in.lx()
                else:
                    end_x = wordline_in.rx() - self.m3_width

                self.add_rect(METAL3, offset=vector(decoder_out.lx(), rail_offset),
                              width=end_x - decoder_out.lx())

                self.add_rect(METAL3, vector(end_x, rail_offset), width=self.m3_width,
                              height=wordline_in.cy() - rail_offset)


class SramOutputMixin(BaselineSram):
    output_operation_start_time = None

    def initialize_operations_start_time(self):
        self.output_operation_start_time = datetime.datetime.now()

    def print_operation_time(self, op_name):
        current_time = datetime.datetime.now()
        print_time(op_name, current_time, self.output_operation_start_time)
        self.output_operation_start_time = current_time

    def save_output_spice_gds(self):
        # Save the spice file and gds
        sp_name = os.path.join(OPTS.output_path, self.name + ".sp")
        gds_name = os.path.join(OPTS.output_path, self.name + ".gds")
        debug.print_str("SP: Writing to {0}".format(sp_name))
        self.sp_write(sp_name)
        self.print_operation_time("Spice writing")
        debug.print_str("GDS: Writing to {0}".format(gds_name))
        self.gds_write(gds_name)
        self.print_operation_time("GDS writing")
        return sp_name, gds_name

    def save_output_pex(self, sp_name, gds_name):
        # Save the extracted spice file
        if OPTS.use_pex:
            import verify
            # Output the extracted design if requested
            sp_file = os.path.join(OPTS.output_path, "temp_pex.sp")
            verify.run_pex(self.name, gds_name, sp_name, output=sp_file)
            self.print_operation_time("Extraction")
        else:
            # Use generated spice file for characterization
            sp_file = sp_name
        return sp_file

    def create_output_lef(self):
        # Create a LEF physical model
        start_time = datetime.datetime.now()
        lefname = os.path.join(OPTS.output_path, self.name + ".lef")
        debug.print_str("LEF: Writing to {0}".format(lefname))
        self.lef_write(lefname)
        self.print_operation_time("LEF")

    def create_output_verilog(self):
        # Write a verilog model
        vname = os.path.join(OPTS.output_path, self.name + ".v")
        debug.print_str("Verilog: Writing to {0}".format(vname))
        self.verilog_write(vname)
        self.print_operation_time("Verilog")

    def characterize_output(self, sp_file, gds_file):
        # Characterize the design
        from characterizer import lib
        debug.print_str("LIB: Characterizing... ")
        if OPTS.analytical_delay:
            debug.print_str("Using analytical delay models (no characterization)")
        else:
            if OPTS.spice_name != "":
                debug.print_str("Performing simulation-based characterization with {}".format(OPTS.spice_name))
            if OPTS.trim_netlist:
                debug.print_str("Trimming netlist to speed up characterization.")
        # TODO use binary simulation optimizer for timing and energy
        # lib(out_dir=OPTS.output_path, sram=self, sp_file=sp_file)
        self.print_operation_time("Characterization")

    def save_output(self):
        """ Save all the output files while reporting time to do it as well. """

        self.initialize_operations_start_time()
        sp_name, gds_name = self.save_output_spice_gds()
        sp_file = self.save_output_pex(sp_name, gds_name)

        self.characterize_output(sp_file, gds_name)
        self.create_output_lef()
        self.create_output_verilog()
