#!/usr/bin/env python3
import os
import re
import sys
from importlib import reload

from char_test_base import CharTestBase


class FlopBufferOptimizer(CharTestBase):
    instantiate_dummy = True

    def runTest(self):

        from globals import OPTS

        from modules.buffer_stage import BufferStage
        from characterizer import stimuli
        import characterizer
        reload(characterizer)

        OPTS.check_lvsdrc = False
        OPTS.logic_height = 1.4
        self.run_drc_lvs = False

        # self.run_pex = False
        self.run_sim = True

        control_buffers_pex = os.path.join(os.getenv("SCRATCH"), "drc_lvs",
                                           "control_buffers.pex.netlist")

        flop_pex = os.path.join(os.getenv("SCRATCH"), "drc_lvs",
                                "ms_flop_horz_pitch_d2.pex.netlist")

        OPTS.control_flop_buffers = stages

        c = reload(__import__(OPTS.control_flop))
        self.mod_flop = getattr(c, OPTS.control_flop)
        self.flop = self.mod_flop()

        buffer_stages = BufferStage(stages, height=self.flop.height, route_outputs=False,
                                    align_bitcell=False)

        buffer_stages_pex = self.run_pex_extraction(buffer_stages, buffer_stages.name,
                                                    run_drc=False, run_lvs=False)

        thresh = 0.45

        self.stim_file_name = self.prefix("stim.sp")

        vdd = 0.9

        with open(self.stim_file_name, "w") as stim_file:
            stim_file.write("simulator lang=spice \n")

            stim = stimuli(stim_file, corner=self.corner)
            stim.write_include(control_buffers_pex)
            stim_file.write('.include "{}"\n'.format(flop_pex))
            stim_file.write('.include "{}"\n'.format(buffer_stages_pex))
            stim.write_supply()

            stim_file.write("Vclk clk gnd PWL ( 0n 0.0v 0.05n 0.0v 0.055n {}v ) \n"
                            .format(vdd))

            # flop
            stim_file.write("Xflop clk gnd flop_out flop_out_bar gnd vdd {}\n".
                            format(self.flop.name))

            # buffers
            if len(stages) % 2 == 0:
                buffer_in = "flop_out"
                buffer_out = "buffer_out_inv buffer_out"
            else:
                buffer_in = "flop_out_bar"
                buffer_out = "buffer_out buffer_out_inv"

            stim_file.write("Xbuffer_stages {} {} vdd gnd {}\n".format(
                buffer_in, buffer_out, buffer_stages.name))

            # control buffers
            output_pins_str = "clk_buf clk_bar wordline_en precharge_en_bar write_en " \
                              "write_en_bar sense_en tri_en tri_en_bar sample_en_bar"
            output_pins = output_pins_str.split()
            stim_file.write("Xcontrol_buffers vdd buffer_out vdd vdd {} vdd gnd {}\n".
                            format(output_pins_str, "control_buffers"))
            for output_pin in output_pins:
                stim_file.write("C{0} {0} gnd {1}\n".format(output_pin, load))

            # initial conditions
            stim_file.write(".ic flop_out={}".format(0.9*vdd))

            # delay measure
            stim_file.write("\n.meas tran dout_delay TRIG v(clk) VAL={0} RISE=1 TD=0n"
                            " TARG v(tri_en_bar) VAL={0} CROSS=1 TD=0n\n\n".format(thresh))

            # simulation run commands
            stim_file.write("\nsimulator lang=spectre\n")
            stim_file.write("simulatorOptions options temp={0} preservenode=all dc_pivot_check=yes"
                            " \n".format(self.corner[2]))

            stim_file.write("tran tran step={} stop={}n ic=node write=spectre.dc \n".
                            format("5p", sim_length))

            stim_file.write("saveOptions options save=lvl nestlvl=1 pwr=total \n")
            stim_file.write("simulator lang=spice \n")

        if self.run_sim:
            stim.run_sim()


load = 10e-15
sim_length = 0.3  # in nano
stages = list(map(float, sys.argv[1].split("#")))
sys.argv.pop(1)

sim_name = "buffer_" + "_".join(["{:.3g}".format(x) for x in stages])
openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "characterization", sim_name)
FlopBufferOptimizer.temp_folder = openram_temp

FlopBufferOptimizer.run_tests(__name__)
