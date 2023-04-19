#!env python3
"""
Test level shifter drc + lvs
Simulate schematic or extracted level shifter to verify functionality
"""
import os

from reram_test_base import ReRamTestBase
from simulator_base import SimulatorBase


class LevelShifterTest(SimulatorBase, ReRamTestBase):

    @classmethod
    def get_sim_directory(cls, cmd_line_opts):
        sim_dir = super().get_sim_directory(cmd_line_opts)
        sim_dir = os.path.join(os.path.dirname(sim_dir), "level_shifter")
        return sim_dir

    @classmethod
    def create_arg_parser(cls):
        parser = super(LevelShifterTest, cls).create_arg_parser()
        parser.add_argument("--vdd_hi", default=3.3, type=float)
        parser.add_argument("--period", default=1.5, type=float)
        parser.add_argument("--slew", default=0.01, type=float)
        return parser

    def create_level_shifter(self):
        from level_shifter import LevelShifter
        bitcell = self.create_class_from_opts("bitcell")
        shifter = LevelShifter(height=2 * bitcell.height)
        return shifter

    def test_level_shifter(self):
        shifter = self.create_level_shifter()
        self.local_check(shifter)

    def test_simulate_level_shifter(self):
        import matplotlib
        matplotlib.use("Qt5Agg")
        import matplotlib.pyplot as plt
        from characterizer.charutils import get_sim_file
        from characterizer.simulation.psf_reader import PsfReader
        from characterizer.simulation.sim_reader import RISING_EDGE
        from globals import OPTS
        from characterizer import stimuli
        options = self.cmd_line_opts
        level_shifter = self.create_level_shifter()

        shifter_spice = os.path.join(OPTS.openram_temp, "level_shifter.sp")
        level_shifter.sp_write(shifter_spice)

        if not options.schematic:
            import verify
            gds_file = os.path.join(OPTS.openram_temp, "level_shifter.gds")
            pex_file = os.path.join(OPTS.openram_temp, "level_shifter.pex.sp")
            level_shifter.gds_write(gds_file)
            verify.run_pex(level_shifter.name, gds_file, shifter_spice,
                           output=pex_file)
            shifter_spice = pex_file

        with open(os.path.join(OPTS.openram_temp, "stim.sp"), "w") as f:
            stim = stimuli(f, corner=self.corner)
            stim.write_include(shifter_spice)
            stim.gen_constant("vdd_hi", options.vdd_hi)
            stim.gen_constant("vdd_lo", stim.voltage)
            stim.gen_constant("gnd", 0)

            # in pulse
            mid_time = 0.5 * options.period
            f.write(f"Vin in 0 PWL ( 0 0 {mid_time - 0.5 * options.slew:.3g}n 0 "
                    f"{mid_time + 0.5 * options.slew:.3g}n {stim.voltage:.3g} )\n")
            # instantiate shifter
            f.write(f"Xshifter {' '.join(level_shifter.pins)} {level_shifter.name}\n")
            f.write(f".probe v(*)\n")

            stim.write_control(options.period)

        stim.run_sim()

        data_file = os.path.join(OPTS.openram_temp, get_sim_file())
        reader = PsfReader(data_file)
        for signal_name in ["in", "out", "out_bar"]:
            signal = reader.get_signal(signal_name)
            plt.plot(reader.time, signal, label=signal_name)

        reader.vdd = options.vdd_hi
        _ = reader.get_transition_time_thresh("out", start_time=0,
                                              edgetype=RISING_EDGE,
                                              thresh=0.5)
        delay = _ * 1e9 - 0.5 * options.period
        print(f"Delay = {delay * 1000:.3g} ps")
        plt.axhline(stim.voltage, linestyle=":")
        plt.axhline(options.vdd_hi, linestyle=":")
        plt.legend()
        plt.grid()
        plt.show()


if __name__ == "__main__":
    LevelShifterTest.parse_options()
    LevelShifterTest.run_tests(__name__)
