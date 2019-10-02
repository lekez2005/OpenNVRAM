#!/usr/bin/env python3

from char_test_base import CharTestBase


class InverterCin(CharTestBase):

    def runTest(self):
        import debug
        from modules.buffer_stage import BufferStage

        out_buffer = BufferStage(buffer_stages=[32, 128], height=self.logic_buffers_height)
        out_pex = self.run_pex_extraction(out_buffer, "out_buffer")

        self.max_c = 10e-15
        self.min_c = 1e-15
        self.start_c = 0.5 * (self.max_c + self.min_c)

        self.load_pex = out_pex
        self.dut_name = out_buffer.name

        self.period = "800ps"

        self.dut_instance = "X4 d f_bar f vdd gnd    {dut_name}          * real load".format(
            dut_name=self.dut_name)

        self.run_optimization()

        with open(self.stim_file_name.replace(".sp", ".log"), "r") as log_file:
            for line in log_file:
                if line.startswith("Optimization completed"):
                    cap_val = float(line.split()[-1])
                    debug.info(1, "Cap = {}fF".format(cap_val*1e15))
                    debug.info(1, "Cap per inverter = {}fF".format(cap_val*1e15/32))


InverterCin.run_tests(__name__)
