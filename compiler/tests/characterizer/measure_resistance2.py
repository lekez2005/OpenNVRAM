#!/usr/bin/env python3

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt

import numpy as np

from char_test_base import CharTestBase


class MeasureResistance(CharTestBase):
    def runTest(self):
        """
        Measure resistance using a large (much larger than Cds/Cdb)
         CLoad such that the delay is essentially R*Cload
         Rise/Fall times should be 2.2*Rp.Cload / 2.2*Rn.Cload
        """
        from modules.buffer_stage import BufferStage
        from characterizer.stimuli import stimuli
        from psf_reader import PsfReader
        from globals import OPTS

        global spice_template

        import debug

        # self.run_pex = False
        self.run_drc_lvs = False

        OPTS.check_lvsdrc = False

        buffer_stages = [1, 1, 4]
        buffer = BufferStage(buffer_stages=buffer_stages, height=self.logic_buffers_height)
        buffer_pex = self.run_pex_extraction(buffer, "buffer")

        vdd_value = self.corner[1]

        cload = 100e-15

        self.period = '2n'

        args = {
            "buffer_name": buffer.name,
            "vdd_value": vdd_value,
            "PERIOD": self.period,
            "TEMPERATURE": self.corner[2],
            "half_vdd": 0.5 * vdd_value,
            "meas_delay": "0.3n",
            "Cload": cload
        }

        spice_content = spice_template.format(**args)

        self.stim_file_name = self.prefix("stim.sp")

        with open(self.stim_file_name, "w") as stim_file:
            stim_file.write("simulator lang=spice \n")
            stim = stimuli(stim_file, corner=self.corner)
            stim.write_include(buffer_pex)
            stim_file.write(spice_content)

        stim.run_sim()

        sim_tran = self.prefix("transient1.tran.tran")
        sim_data = PsfReader(sim_tran)

        out_data = sim_data.get_signal('out_bar')
        time = sim_data.time

        low_thresh = 0.1*vdd_value
        high_thresh = 0.9*vdd_value

        # last rise
        lows = np.diff((out_data - low_thresh) > 0)
        highs = np.diff((out_data - high_thresh) > 0)


        low_indices = []
        high_indices = []

        for i in range(len(lows)):
            if lows[i]:
                low_indices.append(i+1)
            if highs[i]:
                high_indices.append(i+1)

        last_rise = [low_indices[-1], high_indices[-1]]
        last_fall = [high_indices[-2], low_indices[-2]]

        rise_time_10_90 = time[last_rise[1]] - time[last_rise[0]]
        fall_time_10_90 = time[last_fall[1]] - time[last_fall[0]]

        r_n = fall_time_10_90/(2.197*cload)*buffer_stages[-1]
        r_p = rise_time_10_90/(2.197*cload)*buffer_stages[-1]

        debug.info(1, "Rise: 10% time = {:.3g} 90% time = {:.3g}".format(time[last_rise[0]], time[last_rise[1]]))
        debug.info(1, "Fall: 90% time = {:.3g} 10% time = {:.3g}".format(time[last_fall[0]], time[last_fall[1]]))

        debug.info(1, "NMOS resistance = {:3g}".format(r_n))
        debug.info(1, "PMOS resistance = {:3g}".format(r_p))

        # 2.197RC

        plt.plot(time, out_data, label="out_bar")

        plt.plot(time, sim_data.get_signal('a'), label="input")
        plt.plot(time, sim_data.get_signal('out'), label="out")
        plt.legend()
        plt.tight_layout()
        plt.show()


spice_template = """
.PARAM PERIOD=800ps
.PARAM PERIOD={PERIOD}
Vdd vdd gnd {vdd_value}
Vin a gnd pulse 0 {vdd_value} 0ps 20ps 20ps '0.5*PERIOD' 'PERIOD'
X1 a out_bar out vdd gnd        {buffer_name}    *
cdelay out_bar gnd '{Cload}'                        * linear capacitance

.meas tran rise_time TRIG V(out) val='{half_vdd}' FALL=1 TD={meas_delay} TARG V(out_bar) val='{half_vdd}' RISE=1 TD={meas_delay}
.meas tran fall_time TRIG V(out) val='{half_vdd}' RISE=1 TD={meas_delay} TARG V(out_bar) val='{half_vdd}' FALL=1 TD={meas_delay}

simulator lang=spectre
dcOp dc write="spectre.dc" readns="spectre.dc" maxiters=150 maxsteps=10000 annotate=status
tran tran stop=3*{PERIOD} annotate=status maxiters=5 errpreset=conservative
saveOptions options save=lvlpub nestlvl=1 pwr=total
simulatorOptions options temp={TEMPERATURE} maxnotes=10 maxwarns=10  preservenode=all topcheck=fixall dc_pivot_check=yes

"""

MeasureResistance.run_tests(__name__)
