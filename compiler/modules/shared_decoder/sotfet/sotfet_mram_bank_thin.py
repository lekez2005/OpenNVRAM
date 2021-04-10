from base.contact import cross_m1m2, m2m3, cross_m2m3, m1m2, m3m4
from base.design import METAL1, METAL3
from base.vector import vector
from globals import OPTS
from modules.baseline_bank import BaselineBank
from modules.shared_decoder.sotfet.sotfet_mram_bank import SotfetMramBank


class SotfetMramBankThin(SotfetMramBank):
    """bank with thin bitcell not supporting 1 word per row"""

    def create_modules(self):
        assert self.words_per_row > 1, "1 word per row not supported"
        if not self.is_left_bank:
            self.rwl_driver = self.create_module("rwl_driver", name="rwl_driver",
                                                 rows=self.num_rows,
                                                 buffer_stages=OPTS.wordline_buffers)
            self.wwl_driver = self.create_module("wwl_driver", name="wwl_driver",
                                                 rows=self.num_rows,
                                                 buffer_stages=OPTS.wordline_buffers)
        BaselineBank.create_modules(self)

    def add_precharge_array(self):
        BaselineBank.add_precharge_array(self)

    def get_precharge_y(self):
        return BaselineBank.get_precharge_y(self)

    def route_precharge(self):
        BaselineBank.route_precharge(self)

    def route_sense_amp(self):
        self.add_vref_pin()
        BaselineBank.route_sense_amp(self)

    def route_bitcell(self):
        """wordline driver wordline to bitcell array wordlines"""
        self.route_bitcell_array_power()

    def get_control_rails_destinations(self):
        destinations = super().get_control_rails_destinations()
        destinations["wwl_en"] = destinations["precharge_en_bar"]
        destinations["rwl_en"] = destinations["precharge_en_bar"]
        return destinations

    @staticmethod
    def get_default_left_rails():
        return ["wwl_en", "rwl_en"]

    @staticmethod
    def get_default_wordline_enables():
        return ["wwl_en", "rwl_en"]

    def route_wordline_driver(self):
        self.route_decoder_in()
        self.route_wordline_in()
        self.route_decoder_enable()
        self.join_wordline_power()

    def route_wordline_in(self):
        for row in range(self.num_rows):
            for in_name, driver in zip(["wwl", "rwl"],
                                       [self.wwl_driver_inst,
                                        self.rwl_driver_inst]):
                out_pin = driver.get_pin("wl[{}]".format(row))
                in_pin = self.bitcell_array_inst. \
                    get_pin("{}[{}]".format(in_name, row))
                self.add_rect(METAL1, offset=out_pin.lc(),
                              height=in_pin.by() - out_pin.cy(),
                              width=out_pin.width())
                via_offset = vector(out_pin.cx(), in_pin.cy())
                self.add_cross_contact_center(cross_m1m2, via_offset,
                                              rotate=False)
                self.add_via_center(m2m3.layer_stack, via_offset, rotate=90)
                offset = vector(out_pin.cx() - 0.5 * m2m3.second_layer_height,
                                in_pin.by())
                self.add_rect(METAL3, offset=offset,
                              width=in_pin.lx() - offset.x,
                              height=in_pin.height())

    def route_decoder_in(self):
        super().route_decoder_in()
        for inst in [self.wwl_driver_inst, self.rwl_driver_inst]:
            for row in range(self.num_rows):
                in_pin = inst.get_pin("in[{}]".format(row))
                offset = vector(in_pin.lx() - 0.5 * m1m2.first_layer_height,
                                in_pin.cy())
                self.add_cross_contact_center(cross_m2m3, offset)
                self.add_cross_contact_center(cross_m1m2, offset, rotate=True)

    def get_intra_array_grid_top(self):
        # below column mux
        power_pins = (self.sense_amp_array_inst.get_pins("vdd") +
                      self.sense_amp_array_inst.get_pins("gnd"))
        return max(power_pins, key=lambda x: x.uy()).uy()

    def get_inter_array_power_grid_offsets(self):
        cell_offsets = self.bitcell_array.bitcell_offsets
        bit_zero_indices = range(0, self.num_cols, self.words_per_row)
        empty_indices = (set(range(self.num_cols)).
                         difference(set(bit_zero_indices)).
                         difference(set(self.occupied_m4_bitcell_indices)))
        empty_indices = list(empty_indices)

        cell_spacing = OPTS.bitcell_vdd_spacing
        candidates = list(range(cell_spacing, self.num_cols, cell_spacing))
        power_grid_indices = set()
        for candidate in candidates:
            closest = empty_indices[min(range(len(empty_indices)),
                                        key=lambda i: abs(empty_indices[i]
                                                          - candidate))]
            power_grid_indices.add(closest)

        self.occupied_m4_bitcell_indices.extend(candidates)
        power_grid_indices = list(sorted(power_grid_indices))
        mid_x_offsets = [x + 0.5 * self.bitcell.width for x in cell_offsets]

        power_groups = {"vdd": [], "gnd": []}

        rail_width = m3m4.second_layer_height
        space = 0.5 * self.m4_space

        for index in power_grid_indices:
            mid_x = mid_x_offsets[index]
            power_groups["vdd"].append(mid_x - space - rail_width)
            power_groups["gnd"].append(mid_x + space)
        return power_groups
