#!/usr/bin/env python3

from char_test_base import CharTestBase


class DrainCapacitance(CharTestBase):

    def add_additional_includes(self, stim_file):
        stim_file.write(".include \"{0}\" \n".format(self.pmos_pex))

    def runTest(self):
        import debug
        from pgates.ptx import ptx
        from globals import OPTS
        from tech import parameter

        from base.design import design

        class mos_wrapper(design):
            def __init__(self, name, mos):
                super().__init__(name)
                inst = self.add_inst(mos.name, mos, offset=[0, 0])
                pin_list = ["D", "G", "S", "B"]
                self.connect_inst(pin_list)
                self.add_mod(mos)
                self.add_pin_list(pin_list)
                for pin_name in ["D", "G", "S"]:
                    self.copy_layout_pin(inst, pin_name, pin_name)

        self.run_drc_lvs = False
        OPTS.check_lvsdrc = False

        size = 1

        load_nmos = mos_wrapper("nmos_wrap",
                                ptx(width=size, mults=4, tx_type="nmos", connect_active=True, connect_poly=True))
        load_pmos = mos_wrapper("pmos_wrap",
                                ptx(width=size*parameter["beta"], mults=4, tx_type="pmos",
                                    connect_active=True, connect_poly=True))

        self.load_pex = self.run_pex_extraction(load_nmos, "nmos")
        self.pmos_pex = self.run_pex_extraction(load_pmos, "pmos")

        self.dut_name = load_nmos.name

        self.max_c = 10e-15
        self.min_c = 1e-15
        self.start_c = 0.5 * (self.max_c + self.min_c)

        vdd_value = self.corner[1]

        self.period = "800ps"

        self.dut_instance = "X4 d gnd gnd gnd    {dut_name}          * real load \n".format(
            dut_name=load_nmos.name)

        self.dut_instance += "X5 d {vdd_value} {vdd_value} {vdd_value} {dut_name}          * real load".format(
            dut_name=load_pmos.name, vdd_value=vdd_value)

        self.run_optimization()

        with open(self.stim_file_name.replace(".sp", ".log"), "r") as log_file:
            for line in log_file:
                if line.startswith("Optimization completed"):
                    cap_val = float(line.split()[-1])
                    debug.info(1, "Cap = {:.3g}fF".format(cap_val*1e15))
                    debug.info(1, "Cap per micron = {:.3g}fF".format(cap_val*1e15))


DrainCapacitance.run_tests(__name__)
