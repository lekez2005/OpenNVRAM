#!/usr/bin/env python3
from char_test_base import CharTestBase


class MeasureGm(CharTestBase):
    @classmethod
    def add_additional_options(cls):
        from pgates_caps import PINV, PNAND2, PNOR2, PNAND3
        cls.parser.add_argument("--gate", default=PINV,
                                choices=[PINV, PNAND2, PNAND3, PNOR2])
        cls.parser.add_argument("-s", "--size",
                                default=1, type=float, help="Inverter size")

    def run_simulation(self):
        from characterizer.charutils import get_measurement_file
        from characterization_utils import search_meas
        from characterizer.stimuli import stimuli
        from globals import OPTS
        from pgates_caps import PgateCaps, PNOR2
        from tech import spice
        gate = self.options.gate
        size = self.options.size

        param_func = PgateCaps.get_pgate_params
        _ = param_func(gate, "A", size, height=self.logic_buffers_height,
                       options=self.options)
        mod, module_args, terminals = _
        dut = mod(**module_args)

        dut_spice = self.prefix("dut.sp")
        dut.sp_write(dut_spice)

        vdd_value = self.corner[1]

        step_size = vdd_value / 20

        dut_pins = dut.pins
        other_pins = dut_pins[1:-3]
        if gate == PNOR2:
            other_pins = ["gnd"] * len(other_pins)
        else:
            other_pins = ["vdd"] * len(other_pins)
        inst_pins = " ".join(["a"] + other_pins + dut_pins[-3:])
        dut_instance = f"Xdut {inst_pins} {dut.name}"

        conn_indices = [i for i, conn in enumerate(dut.conns) if "A" in conn]
        nmos_index, pmos_index = sorted(conn_indices,
                                        key=lambda x: "vdd" in dut.conns[x])
        nmos_inst = dut.insts[nmos_index]
        pmos_inst = dut.insts[pmos_index]

        nmos_mod = pmos_mod = ""
        if "subckt_nmos" in spice:
            nmos_mod = f".{spice['subckt_nmos']}"
        if "subckt_pmos" in spice:
            pmos_mod = f".{spice['subckt_pmos']}"

        kwargs = {
            "vdd_value": vdd_value,
            "step_size": step_size,
            "nmos_name": nmos_inst.name, "nmos_mod": nmos_mod,
            "pmos_name": pmos_inst.name, "pmos_mod": pmos_mod,
            "dut_instance": dut_instance
        }

        self.stim_file_name = self.prefix("stim.sp")
        with open(self.stim_file_name, "w") as stim_file:
            stim_file.write(spice_template.format(**kwargs))
            stim = stimuli(stim_file, corner=self.corner)
            stim.write_include(dut_spice)

        ret_code = stim.run_sim()
        assert ret_code == 0

        if OPTS.spice_name == "hspice":
            # TODO fragile
            meas_file = self.prefix("timing.ms0")
            with open(meas_file, "r") as f:
                content = f.read().strip().split("\n")[-1].strip()
                gm_nmos, gm_pmos = map(float, content.split()[:2])
        else:
            meas_file = self.prefix(get_measurement_file())
            gm_nmos = float(search_meas("gm_nmos", meas_file))
            gm_pmos = float(search_meas("gm_pmos", meas_file))

        return gm_nmos, gm_pmos, nmos_inst, pmos_inst, dut

    def test_single_sim(self):
        from tech import spice as tech_spice

        gm_nmos, gm_pmos, nmos_inst, pmos_inst, dut = self.run_simulation()
        if tech_spice["scale_tx_parameters"]:
            tx_scale = 1e6
        else:
            tx_scale = 1
        for gm, inst, name in zip([gm_nmos, gm_pmos], [nmos_inst, pmos_inst],
                                  ["nmos", "pmos"]):
            tx_width = inst.mod.tx_width * tx_scale
            gm_per_unit = 1e6 * gm * tech_spice["minwidth_tx"] / tx_width
            print(f"gm per min-width for {dut.name} = {name}: {gm_per_unit:5.5g}u")


spice_template = """
.OPTIONS POST=2 PSf=1
Vgnd gnd 0 0
Vdd vdd gnd {vdd_value}
Vin a gnd dc 0
{dut_instance}
.print dc LX7(Xdut.X{nmos_name}{nmos_mod})
.print dc LX7(Xdut.X{pmos_name}{pmos_mod})
.measure dc gm_nmos max LX7(Xdut.X{nmos_name}{nmos_mod})
.measure dc gm_pmos max LX7(Xdut.X{pmos_name}{pmos_mod})
.dc Vin 0, {vdd_value}, {step_size}
"""

MeasureGm.run_tests(__name__)
