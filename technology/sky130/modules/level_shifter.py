from base.analog_cell_mixin import AnalogMixin
from base.contact import m1m2
from base.design import design, METAL2, NWELL, METAL1, TAP_ACTIVE
from base.flatten_layout import flatten_rects
from base.layout_clearances import combine_rects
from base.unique_meta import Unique
from base.utils import round_to_grid as rg
from base.vector import vector
from base.well_active_contacts import add_power_tap
from globals import OPTS
from pgates.pgate import pgate
from pgates.pinv import pinv
from pgates.ptx_spice import ptx_spice
from tech import drc


class LevelShifter(design, metaclass=Unique):

    @classmethod
    def get_name(cls, height=None, align_bitcell=False):
        name = "level_shifter"
        if height is not None:
            name += f"_h{height:.3g}"
        if align_bitcell:
            name += "_align_bitcell"
        return name.replace(".", "__")

    def __init__(self, height=None, align_bitcell=False):
        from tech import add_tech_layers
        super().__init__(self.get_name(height, align_bitcell))
        self.height, _ = pgate.get_height(height, align_bitcell)
        self.create_layout()
        self.create_spice()
        add_tech_layers(self)

    def create_spice(self):
        from devices_5v import ptx_spice_5v
        self.add_pin_list(["in", "out", "out_bar", "vdd_lo", "vdd_hi", "gnd"])

        offset = vector(0, 0)
        # create inverter spice
        inverter_nmos = ptx_spice(width=self.inverter.nmos_width, tx_type=self.nmos.tx_type)
        inverter_pmos = ptx_spice(width=self.inverter.pmos_width, tx_type=self.pmos.tx_type)

        self.add_inst("inv_nmos", inverter_nmos, offset)
        self.connect_inst(["in_bar", "in", "gnd", "gnd"])
        self.add_inst("inv_pmos", inverter_pmos, offset)
        self.connect_inst(["in_bar", "in", "vdd_lo", "vdd_lo"])

        # create nmos and pmos spice
        for inst in [self.nmos_inst, self.pmos_inst]:
            flatten_rects(self, [inst], [self.insts.index(inst)],
                          skip_export_spice=True)

        nmos_spice = ptx_spice_5v(width=self.nmos.tx_width, mults=1, tx_type=self.nmos.tx_type,
                                  tx_length=self.nmos.tx_length)
        self.add_mod(nmos_spice)

        self.add_inst("out_bar_nmos", nmos_spice, offset)
        self.connect_inst(["out_bar", "in", "gnd", "gnd"])
        self.add_inst("out_nmos", nmos_spice, offset)
        self.connect_inst(["out", "in_bar", "gnd", "gnd"])

        pmos_spice = ptx_spice_5v(width=self.pmos.tx_width, mults=1, tx_type=self.pmos.tx_type,
                                  tx_length=self.pmos.tx_length)
        self.add_mod(pmos_spice)
        self.add_inst("out_bar_pmos", pmos_spice, offset)
        self.connect_inst(["out_bar", "out", "vdd_hi", "vdd_hi"])
        self.add_inst("out_pmos", pmos_spice, offset)
        self.connect_inst(["out", "out_bar", "vdd_hi", "vdd_hi"])

    def create_layout(self):
        self.add_input_inverter()
        self.add_shifter()
        self.add_shifter_power()
        self.route_shifter_inputs()
        self.route_shifter_outputs()
        self.move_inverter_output_pin()
        self.add_boundary()

    def add_input_inverter(self):
        self.inverter = inverter = pinv(size=1, height=self.height)
        self.add_mod(inverter)

        self.inv_inst = self.add_inst("input_inverter", mod=inverter, offset=vector(0, 0))
        self.connect_inst(["in", "in_bar", "vdd_lo", "gnd"])

        self.copy_layout_pin(self.inv_inst, "A", "in")
        self.copy_layout_pin(self.inv_inst, "vdd", "vdd_lo")

        # add pin from source to power
        pmos_active = ptx_spice.get_mos_active(inverter, tx_type="p", recursive=True)[0]
        x_offset = inverter.source_positions[0] - 0.5 * self.m1_width
        self.add_layout_pin("vdd_lo", METAL1, vector(x_offset, pmos_active.cy()),
                            height=self.height - pmos_active.cy())

    def move_inverter_output_pin(self):
        # move output pin to m2
        output_pin = self.inv_inst.get_pin("z")

        flatten_rects(self, [self.inv_inst], [self.insts.index(self.inv_inst)],
                      skip_export_spice=True)
        indices = []
        for rect_index, rect in enumerate(self.objs):
            if (rg(rect.cx()) == rg(output_pin.cx()) and
                    rg(rect.cy() == rg(output_pin.cy()))):
                indices.append(rect_index)

        for rect_index in indices:
            rect = self.objs[rect_index]
            self.add_rect(METAL2, rect.ll(), width=rect.width,
                          height=rect.height)
        self.objs = [self.objs[i] for i in range(len(self.objs)) if i not in indices]

    def add_shifter(self):
        from devices_5v import ptx_5v
        nmos_width = OPTS.level_shifter_nmos_width
        self.nmos = nmos = ptx_5v(width=nmos_width, mults=2, tx_type="nmos", contact_poly=True,
                                  connect_poly=False)

        pmos_width = OPTS.level_shifter_pmos_width
        self.pmos = pmos = ptx_5v(width=pmos_width, mults=2, tx_type="pmos", contact_poly=True,
                                  connect_poly=False)

        nmos_gate = nmos.get_pins("G")[0]
        in_pin = self.get_pin("in")
        # TODO handle when nmos height > inverter gate pin
        nmos_y = in_pin.cy() - nmos_gate.cy()

        well_space = drc.get("high_voltage_well_space")
        inverter_nwell = self.inv_inst.mod.get_max_shape(NWELL, "rx")
        pmos_nwell = pmos.get_max_shape(NWELL, "lx")
        x_space = ((inverter_nwell.rx() - self.inv_inst.mod.width) - pmos_nwell.lx() +
                   well_space)

        x_offset = self.inv_inst.rx() + x_space
        self.nmos_inst = self.add_inst("shift_nmos", mod=nmos, offset=vector(x_offset, nmos_y))
        self.connect_inst([], check=False)

        pmos_gate = pmos.get_pins("G")[0]
        self.in_bar_mid_y = (self.nmos_inst.get_pins("G")[0].uy() + self.line_end_space +
                             0.5 * self.m1_width)

        self.out_rail_mid_y = (self.in_bar_mid_y + 0.5 * self.m1_width + self.line_end_space +
                               0.5 * self.m1_width)

        pmos_y = self.out_rail_mid_y + 0.5 * self.m1_width + self.line_end_space + pmos_gate.by()
        self.pmos_inst = self.add_inst("shift_pmos", mod=pmos, offset=vector(x_offset, pmos_y))
        self.connect_inst([], check=False)

    def add_shifter_power(self):
        pmos_nwell = self.pmos_inst.get_max_shape(NWELL, "uy")
        pin_mid_x = pmos_nwell.cx()

        enclosure = self.nmos.well_enclose_active
        pin_width = pmos_nwell.width - 2 * enclosure
        self.width = pin_width

        vdd_pin, nwell_cont, _ = add_power_tap(self, self.height - 0.5 * self.rail_height, "vdd_hi",
                                               pin_width=pin_width, pin_center_x=pin_mid_x)

        gnd_pin, _, _ = add_power_tap(self, -0.5 * self.rail_height, "gnd",
                                      pin_width=pin_width, pin_center_x=pin_mid_x)
        self.add_rect(METAL1, vector(0, gnd_pin.by()), height=gnd_pin.height(),
                      width=gnd_pin.rx())

        # combine nwell
        cont_tap_active = nwell_cont.get_max_shape(TAP_ACTIVE, "uy")
        cont_well = nwell_cont.get_max_shape(NWELL, "uy")
        tx_well = self.pmos_inst.get_max_shape(NWELL, "uy")
        combined_rect = combine_rects(cont_well, tx_well)

        well_enclose_active = self.pmos.well_enclose_active
        well_top = max(combined_rect.uy(), cont_tap_active.uy() + well_enclose_active)
        self.add_rect(NWELL, combined_rect.ll(), width=combined_rect.width,
                      height=well_top - combined_rect.by())

        self.width = gnd_pin.rx()

        # drains to pins
        for i in range(2):
            tx_inst = [self.nmos_inst, self.pmos_inst][i]
            drain_pin = tx_inst.get_pin("D")
            power_pin = [gnd_pin, vdd_pin][i]

            rail_width = 3 * drain_pin.width()
            y_offset = drain_pin.uy() if i == 0 else drain_pin.by()
            self.add_rect(METAL1, vector(drain_pin.cx() - 0.5 * rail_width, y_offset),
                          width=rail_width, height=power_pin.cy() - y_offset)

    def route_shifter_inputs(self):
        nmos_gates = list(sorted(self.nmos_inst.get_pins("G"), key=lambda x: x.lx()))
        # in
        in_inverter = self.get_pin("in")
        in_nmos = nmos_gates[0]
        self.add_rect(METAL1, offset=in_inverter.center() - vector(0, 0.5 * self.m1_width),
                      width=in_nmos.cx() - in_inverter.cx())
        # in_bar
        in_bar_inverter = self.inv_inst.get_pin("z")
        in_bar_nmos = nmos_gates[1]
        offset = vector(in_bar_inverter.cx(), self.in_bar_mid_y - 0.5 * self.m1_width)
        self.add_rect(METAL1, offset=offset, width=in_bar_nmos.cx() - offset.x)
        self.add_rect(METAL1, in_bar_nmos.ul(), width=in_bar_nmos.width(),
                      height=offset.y + self.m1_width - in_bar_nmos.uy())
        via_offset = vector(in_bar_inverter.cx(), offset.y + 0.5 * m1m2.h_1)
        self.add_contact_center(m1m2.layer_stack, offset=via_offset)

    def route_shifter_outputs(self):
        nmos_pins = AnalogMixin.get_sorted_pins(self.nmos_inst, "S")
        pmos_pins = AnalogMixin.get_sorted_pins(self.pmos_inst, "S")
        rail_width = m1m2.w_2
        for i in range(2):
            nmos_pin = nmos_pins[i]
            pmos_pin = pmos_pins[i]
            for pin in [nmos_pin, pmos_pin]:
                self.add_contact_center(m1m2.layer_stack, pin.center())

            offset = nmos_pin.center() - vector(0.5 * rail_width, 0)
            height = pmos_pin.cy() - nmos_pin.cy()
            pin_name = "out_bar" if i == 0 else "out"
            self.add_layout_pin(pin_name, METAL2, offset, width=rail_width, height=height)
        gate_pins = AnalogMixin.get_sorted_pins(self.pmos_inst, "G")
        # out_bar
        out_bar_gate = gate_pins[1]
        out_bar_drain = pmos_pins[0]
        x_offset = min(out_bar_gate.cx(), pmos_pins[1].cx() - 0.5 * rail_width - self.m2_space)
        self.add_contact_center(m1m2.layer_stack, vector(x_offset, out_bar_gate.cy()))
        self.add_rect(METAL2, vector(out_bar_drain.cx(), out_bar_gate.cy() - 0.5 * self.m2_width),
                      width=out_bar_gate.cx() - out_bar_drain.cx())

        # out
        y_offset = self.out_rail_mid_y
        out_gate = gate_pins[0]
        out_drain = pmos_pins[1]
        self.add_contact_center(m1m2.layer_stack, vector(out_drain.cx(), y_offset))
        y_offset = y_offset - 0.5 * self.m1_width
        self.add_rect(METAL1, vector(out_gate.cx(), y_offset),
                      width=out_drain.cx() - out_gate.cx())
        self.add_rect(METAL1, vector(out_gate.lx(), y_offset), height=out_gate.by() - y_offset)
