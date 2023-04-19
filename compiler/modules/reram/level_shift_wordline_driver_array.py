from base.analog_cell_mixin import AnalogMixin
from base.contact import m1m2, m2m3, m3m4
from base.design import design, METAL2, METAL3, METAL4, NWELL
from base.layout_clearances import extract_unique_rects
from base.unique_meta import Unique
from base.utils import round_to_grid as rg
from base.vector import vector
from base.well_implant_fills import evaluate_module_space_by_layer
from devices_5v import pinv_5v
from globals import OPTS
from level_shifter import LevelShifter
from modules.bitcell_vertical_aligned import BitcellVerticalAligned
from modules.buffer_stage import BufferStage
from modules.stacked_wordline_driver_array import stacked_wordline_driver_array
from pgates.pnand2 import pnand2
from pgates.pnor2 import pnor2
from tech import add_tech_layers, drc


class HighVoltageBufferStage(BufferStage):
    @classmethod
    def get_name(cls, *args, **kwargs):
        return super().get_name(*args, **kwargs) + "_hv"

    def create_buffer_inv(self, size, index=None):
        return pinv_5v(size=size, height=self.height, contact_nwell=self.contact_nwell,
                       contact_pwell=self.contact_pwell, align_bitcell=self.align_bitcell,
                       fake_contacts=self.fake_contacts)


class LevelShiftWordlineDriver(design, metaclass=Unique):

    @classmethod
    def get_name(cls, buffer_stages, logic, height):
        buffer_stages_str = "_".join(['{:.3g}'.format(x) for x in buffer_stages])
        name = f"level_shifter_driver_{logic}_{buffer_stages_str}_h_{height:.3g}"
        return name.replace(".", "__")

    def __init__(self, buffer_stages, logic, height):
        name = self.get_name(buffer_stages, logic, height)
        super().__init__(name)
        self.buffer_stages = buffer_stages
        self.logic_str = logic
        self.height = height
        self.create_layout()
        self.add_pins()

    def create_layout(self):
        self.create_modules()
        self.add_modules()
        self.join_nwells()
        self.route_layout()
        self.add_power_pins()
        add_tech_layers(self)
        self.add_boundary()

    def add_pins(self):
        self.add_pin_list(["A", "B", "out_inv", "out", "vdd_lo", "vdd", "gnd"])

    def create_modules(self):
        self.buffer_mod = HighVoltageBufferStage(buffer_stages=self.buffer_stages,
                                                 height=self.height,
                                                 route_outputs=False, align_bitcell=True,
                                                 contact_nwell=False, contact_pwell=False)
        self.add_mod(self.buffer_mod)
        logic_class = {"pnand2": pnand2, "pnor2": pnor2}.get(self.logic_str)
        self.logic_mod = logic_class(height=self.height,
                                     contact_nwell=False, contact_pwell=False,
                                     align_bitcell=True, same_line_inputs=True)
        self.add_mod(self.logic_mod)

        self.level_shifter = LevelShifter(height=self.height, align_bitcell=True)
        self.add_mod(self.level_shifter)

    def add_modules(self):
        # logic
        self.logic_inst = self.add_inst("logic", self.logic_mod, offset=vector(0, 0))
        self.connect_inst(["A", "B", "logic_out", "vdd_lo", "gnd"])
        self.copy_layout_pin(self.logic_inst, "A")
        self.copy_layout_pin(self.logic_inst, "B")
        # level shifter
        shifter_inverter = self.level_shifter.inverter
        min_space = self.logic_mod.calculate_min_space(self.logic_mod, shifter_inverter)
        x_offset = self.logic_inst.rx() + min_space + self.level_shifter.inv_inst.lx()
        self.shifter_inst = self.add_inst("shifter", self.level_shifter, offset=vector(x_offset, 0))
        self.connect_inst(["logic_out", "logic_out_shifted", "logic_out_shifted_bar",
                           "vdd_lo", "vdd", "gnd"])
        # buffer stages
        min_space = self.logic_mod.calculate_min_space(self.level_shifter, self.buffer_mod)
        offset = self.shifter_inst.lr() + vector(min_space, 0)
        self.buffer_inst = self.add_inst("buffer", self.buffer_mod, offset=offset)
        self.connect_inst(["logic_out_shifted", "out", "out_inv", "vdd", "gnd"])

        self.copy_layout_pin(self.buffer_inst, "out_inv", "out")
        self.copy_layout_pin(self.buffer_inst, "out", "out_inv")

        self.width = self.buffer_inst.rx()

    def join_nwells(self):
        shifter_well = self.shifter_inst.get_max_shape(NWELL, "rx", recursive=True)
        buffer_well = self.buffer_inst.get_max_shape(NWELL, "lx", recursive=True)
        if rg(buffer_well.lx()) > rg(shifter_well.rx()):
            y_offset = max(buffer_well.by(), shifter_well.by())
            height = max(buffer_well.uy(), shifter_well.uy()) - y_offset
            self.add_rect(NWELL, vector(shifter_well.rx(), y_offset),
                          width=buffer_well.lx() - shifter_well.rx(),
                          height=height)

    def route_layout(self):
        insts = [(self.logic_inst, self.shifter_inst), (self.shifter_inst, self.buffer_inst)]
        input_names = ["in", "in"]
        output_names = ["z", "out"]
        for i in range(2):
            left_inst, right_inst = insts[i]
            input_pin = right_inst.get_pin(input_names[i])
            output_pin = left_inst.get_pin(output_names[i])
            layer = output_pin.layer
            offset = vector(output_pin.cx(),
                            input_pin.cy() - 0.5 * self.get_min_layer_width(layer))
            self.add_rect(output_pin.layer, offset, width=input_pin.cx() - offset.x)
            if layer == METAL2:
                self.add_contact_center(m1m2.layer_stack, input_pin.center())

    def add_power_pins(self):
        for pin_name in ["vdd", "gnd"]:
            pin = self.buffer_inst.get_pin(pin_name)
            if pin_name == "vdd":
                x_offset = self.shifter_inst.get_pin("vdd_hi").lx()
            else:
                x_offset = 0

            m1_rect = self.add_rect(pin.layer, vector(x_offset, pin.by()),
                                    height=pin.height(), width=pin.rx() - x_offset)
            AnalogMixin.add_m1_m3_power_via(self, m1_rect, recursive=False,
                                            existing=[(x_offset, self.width)],
                                            add_m3_pin=False)
            self.add_layout_pin(pin_name, METAL3, vector(0, m1_rect.by()), width=self.width,
                                height=pin.height())

        # vdd lo
        all_vdd_lo = self.shifter_inst.get_pins("vdd_lo")
        vdd_lo = [pin for pin in all_vdd_lo if pin.height() > pin.width()][0]
        pin_width = 1.5 * self.m4_width
        mid_x = vdd_lo.cx()
        self.add_layout_pin("vdd_lo", METAL4, vector(mid_x - 0.5 * pin_width, 0),
                            width=pin_width, height=self.height)
        via_m3_height = max(m2m3.h_2, m3m4.h_1)
        via_y = self.height - 0.5 * self.rail_height - self.m3_space - 0.5 * via_m3_height
        for via in [m1m2, m2m3, m3m4]:
            self.add_contact_center(via.layer_stack, vector(mid_x, via_y))


class LevelShiftWordlineDriverArray(stacked_wordline_driver_array):
    def add_pins(self):
        super().add_pins()
        self.add_pin("vdd_lo")

    def get_connections(self, row):
        outputs = [f"wl_bar[{row}]", f"wl[{row}]"]
        if len(self.buffer_stages) % 2 == 0:
            outputs = list(reversed(outputs))
        return ["en", f"in[{row}]"] + outputs + ["vdd_lo", "vdd", "gnd"]

    def create_modules(self):
        self.bitcell = self.create_mod_from_str(OPTS.bitcell)
        self.logic_buffer = LevelShiftWordlineDriver(self.buffer_stages, logic="pnand2",
                                                     height=2 * self.bitcell.height)
        self.add_mod(self.logic_buffer)

    def get_en_rail_y(self, en_rail):
        return en_rail.by() - m2m3.h_2 - self.m3_space

    def get_pin_and_inst_offsets(self):
        well_space = drc.get("high_voltage_well_space")
        mod_space = evaluate_module_space_by_layer(self.logic_buffer, self.logic_buffer,
                                                   layer=NWELL, recursive=True,
                                                   min_space=well_space)
        (en_rail_x, en_pin_x), inst_offsets = super().get_pin_and_inst_offsets()
        inst_offsets[1] = inst_offsets[0] + self.logic_buffer.width + mod_space
        en_pin_x = inst_offsets[1] - inst_offsets[0]
        return (en_rail_x, en_pin_x), inst_offsets

    def fill_horizontal_module_space(self):
        pass

    def create_power_pins(self):
        super().create_power_pins()
        self.fill_tap_well()
        # create m4 vdd_lo pin
        for col_index, inst in enumerate(self.buffer_insts[:2]):
            vdd_lo = inst.get_pin("vdd_lo")
            self.add_layout_pin(vdd_lo.name, vdd_lo.layer, vdd_lo.ll(),
                                width=vdd_lo.width(), height=self.height - vdd_lo.by())
            # create m4 gnd pin next to vdd_lo
            x_offset = vdd_lo.rx() + self.m4_space
            gnd_pin = self.add_layout_pin("gnd", vdd_lo.layer,
                                          offset=vector(x_offset, vdd_lo.by()),
                                          width=vdd_lo.width(), height=self.height - vdd_lo.by())
            for row_inst in self.buffer_insts[col_index::2]:
                inst_pins = row_inst.get_pins("gnd")
                inst_pins = [pin for pin in inst_pins if pin.layer == METAL3]
                for inst_pin in inst_pins:
                    self.add_contact_center(m3m4.layer_stack,
                                            vector(gnd_pin.cx(), inst_pin.cy()))

    def fill_tap_well(self):
        # fill space between adjacent NWELLs caused by inserting body tap
        for inst in self.buffer_insts[:2]:
            nwell_rects = inst.get_layer_shapes(NWELL, recursive=True)
            nwell_rects = [x for x in nwell_rects if x.by() < inst.by()]
            nwell_rects = extract_unique_rects(nwell_rects, min_space=0)

            for y_offset, y_top in BitcellVerticalAligned.calculate_nwell_y_fills(self):
                for nwell_rect in nwell_rects:
                    self.add_rect(NWELL, vector(nwell_rect.lx(), y_offset),
                                  height=y_top - y_offset,
                                  width=nwell_rect.width)

    def add_body_taps(self):
        pass
