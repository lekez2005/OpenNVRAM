#!/usr/bin/env python3

from char_test_base import CharTestBase


class MeasureResistance(CharTestBase):
    """
    """
    def runTest(self):
        from modules.buffer_stage import BufferStage
        from characterizer.stimuli import stimuli

        fail = True
        if fail:
            assert False, "Use measure_resistance2 instead, this implementation uses delay instead of rise/fall times" \
                          "resulting in incorrect results"

        import debug

        rise_times = []
        fall_times = []

        stages = [
            [1, 3],
            [1, 4]
        ]

        for i in range(2):
            buffer = BufferStage(buffer_stages=stages[i], height=self.logic_buffers_height)
            buffer_pex = self.run_pex_extraction(buffer, "buffer")

            spice_template = open("resistance_template.sp").read()
            vdd_value = self.corner[1]
            args = {
                "buffer_name": buffer.name,
                "vdd_value": vdd_value,
                "PERIOD": self.period,
                "TEMPERATURE": self.corner[2],
                "half_vdd": 0.5 * vdd_value,
                "meas_delay": "0.3n"
            }

            spice_content = spice_template.format(**args)

            self.stim_file_name = self.prefix("stim.sp")

            with open(self.stim_file_name, "w") as stim_file:
                stim_file.write("simulator lang=spice \n")
                stim = stimuli(stim_file, corner=self.corner)
                stim.write_include(buffer_pex)
                stim_file.write(spice_content)

            stim.run_sim()

            with open(self.prefix("stim.measure"), "r") as meas_file:
                rise_time = fall_time = 0
                for line in meas_file:
                    if line.startswith("fall_time"):
                        fall_time = float(line.split()[-1])
                    if line.startswith("rise_time"):
                        rise_time = float(line.split()[-1])
                rise_times.append(rise_time)
                fall_times.append(fall_time)

        delta_rise = rise_times[1] - rise_times[0]
        delta_fall = fall_times[1] - fall_times[0]

        Cg = 0.191e-15
        Rp = delta_rise/(3*Cg)
        Rn = delta_fall/(3*Cg)

        debug.info(1, "NMOS resistance = {}".format(Rn))
        debug.info(1, "PMOS resistance = {}".format(Rp))


MeasureResistance.run_tests(__name__)
