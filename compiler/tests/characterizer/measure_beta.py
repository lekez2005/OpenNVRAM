#!/usr/bin/env python3

from char_test_base import CharTestBase
import numpy as np


class MeasureBeta(CharTestBase):
    def runTest(self):
        from modules.buffer_stage import BufferStage
        from characterizer.stimuli import stimuli
        from pgates.pinv import pinv
        from tech import parameter
        from globals import OPTS
        import debug
        from base.design import design

        self.run_drc_lvs = False
        OPTS.check_lvsdrc = False

        cload = 60e-15

        # for beta in np.linspace(1.7, 2.2, 2):
        all_beta = np.linspace(1.3, 2.2, 100)
        averages = {}
        rise_times = {}
        fall_times = {}
        for i in range(len(all_beta)):
            beta = all_beta[i]
            parameter["beta"] = beta
            # in buffer
            buffer = BufferStage(buffer_stages=[1, 4, 16], height=self.logic_buffers_height)

            buffer_pex = self.run_pex_extraction(buffer, "buffer")

            debug.info(1, "beta = {}".format(beta))

            spice_template = open("beta_template.sp").read()
            vdd_value = self.corner[1]
            args = {
                "buffer_name": buffer.name,
                "vdd_value": vdd_value,
                "PERIOD": self.period,
                "TEMPERATURE": self.corner[2],
                "half_vdd": 0.5 * vdd_value,
                "Cload": cload,
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
                        fall_time = float(line.split()[-1])*1e12
                    if line.startswith("rise_time"):
                        rise_time = float(line.split()[-1])*1e12

                rise_times[beta] = rise_time
                fall_times[beta] = fall_time
                averages[beta] = 0.5*(rise_time + fall_time)
                debug.info(1, "Best beta = {}".format(min(averages, key=averages.get)))

            # reset cache to force recreating inverters with latest beta
            pinv._cache = {}
            BufferStage._cache = {}
            design.name_map = []

            #
        print("rise times: ")
        print(rise_times)
        print("fall times: ")
        print(fall_times)
        print(averages)
        print("Best beta = ", min(averages, key=averages.get))

        try:
            import matplotlib
            matplotlib.use("Qt5Agg")
            import matplotlib.pyplot as plt
            plt.plot(averages.keys(), [averages[key] for key in averages.keys()])
            plt.show()
        except ImportError:
            pass


MeasureBeta.run_tests(__name__)
