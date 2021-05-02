#!/usr/bin/env python3
import itertools
from importlib import reload

from char_test_base import CharTestBase



class WordlineDriverOptimizer(CharTestBase):
    instantiate_dummy = True

    def runTest(self):

        from globals import OPTS

        from modules.logic_buffer import LogicBuffer
        from psf_reader import PsfReader
        import numpy as np
        from characterizer import stimuli
        import characterizer
        reload(characterizer)
        from base.design import design
        from wordline_en_optimizer import WordlineEnOptimizer
        from modules.bitcell_array import bitcell_array

        OPTS.check_lvsdrc = False
        OPTS.wire_length = 35
        OPTS.num_rows = num_rows = 128
        OPTS.num_cols = 256
        OPTS.logic_height = 1.4

        thresh = 0.45
        N = 12
        MAX_SIZE = 40

        buffer_size = 30

        # wordline_en_driver
        buffer_stages = [(buffer_size ** (1 / 3)) ** x for x in range(4)]
        wordline_buf = LogicBuffer(buffer_stages=buffer_stages, logic="pnor2",
                                   height=OPTS.logic_height)

        self.run_pex = False
        wordline_en_pex = self.run_pex_extraction(wordline_buf, "wl_en_driver", run_drc=False, run_lvs=False)

        # bitcell array

        self.run_pex = False
        cell_array = bitcell_array(cols=OPTS.num_cols, rows=1)
        bitcell_pex = self.run_pex_extraction(cell_array, "bitcell_array", run_drc=False, run_lvs=False)

        self.run_drc_lvs = False

        self.stim_file_name = self.prefix("stim.sp")

        end_time = 4

        self.run_lvs = False
        self.run_pex = True
        self.run_sim = True

        vdd = 0.9

        in_pin_name = "in_driver"
        output_name = "v(Xbitcell_array.N_wl[0]_Xbit_r0_c{}_M1_g)".format(OPTS.num_cols-1)
        en_name = "v(Xdut.N_en_Xdriver_array_Xdriver{}_Xlogic_Mpnand2_nmos2_g)".format(OPTS.num_rows-1)

        delays = np.zeros([N, 4], np.double)
        # buffer_sizes = np.logspace(0, np.log10(MAX_SIZE), N)
        buffer_sizes = np.linspace(2, MAX_SIZE, N)

        half_N = int(N/2)

        buffer_sizes = [x for x in itertools.chain(
            *itertools.zip_longest(buffer_sizes[:half_N],
                                   list(reversed(buffer_sizes))[:N-half_N])) if x is not None]

        for i in range(N):
            buffer_size = buffer_sizes[i]

            design.name_map = []

            OPTS.wordline_buffers = [(buffer_size**(1/2))**x for x in range(3)]
            print(OPTS.wordline_buffers)
            wl_driver = WordlineEnOptimizer.make_wordline_driver()()

            wl_driver_pex = self.run_pex_extraction(wl_driver, "wl_driver", run_drc=False, run_lvs=self.run_lvs)

            with open(self.stim_file_name, "w") as stim_file:
                stim_file.write("simulator lang=spice \n")

                stim = stimuli(stim_file, corner=self.corner)
                stim.write_include(bitcell_pex)
                stim_file.write('.include "{}"\n'.format(wordline_en_pex))
                stim_file.write('.include "{}"\n'.format(wl_driver_pex))

                stim.write_supply()

                stim_file.write("V{} {} gnd PWL ( 0n 0.9v 0.3n 0.9v 0.31n 0v 2n 0v 2.01n 0.9v ) \n"
                                .format(in_pin_name, in_pin_name))

                # stim_file.write("R1 sampleb_1 sampleb {} \n".format(r_driver))
                for j in range(OPTS.num_rows-1):
                    in_name = "in[{}]".format(j)
                    stim_file.write("V{} {} 0 0\n".format(in_name, in_name))

                stim_file.write("Vin[{}] in[{}] 0 {}\n".format(num_rows-1, num_rows-1, vdd))

                # en
                stim_file.write("Xdut {} {} \n".format(" ".join(wl_driver.pins), wl_driver.name))

                # driver
                stim_file.write("Xdriver gnd {} en float vdd gnd {} \n".format(in_pin_name, wordline_buf.name))

                # bitcell
                # replace wl[0] with wl[N-1]
                terminals = " ".join(cell_array.pins).replace("wl[0]", "wl[{}]".format(num_rows-1))
                stim_file.write("Xbitcell_array {} {} \n".format(terminals, cell_array.name))

                stim_file.write("\nsimulator lang=spectre\n")
                stim_file.write("simulatorOptions options temp={0} preservenode=all dc_pivot_check=yes"
                                " \n".format(self.corner[2]))

                stim_file.write("tran tran step={} stop={}n ic=node write=spectre.dc \n".format("5p", end_time))

                stim_file.write("saveOptions options save=lvl nestlvl=1 pwr=total \n")
                stim_file.write("simulator lang=spice \n")

                for j in range(num_rows):
                    stim_file.write(".probe v(wl[{}]) \n".format(j))

                stim_file.write(".probe {} \n".format(output_name))
                stim_file.write(".probe {} \n".format(en_name))

            if self.run_sim:
                stim.run_sim()
            sim_data = PsfReader(self.prefix("transient1.tran.tran"))
            delay1 = sim_data.get_delay(en_name,
                                       output_name, thresh1=thresh, thresh2=thresh)
            delays[i][0] = buffer_size
            delays[i][1] = delay1*1e12

            delay2 = sim_data.get_delay(in_pin_name,
                                        output_name, thresh1=thresh, thresh2=thresh)
            delays[i][3] = delay2*1e12

            current = sim_data.get_signal('Vvdd:p')
            energy = -np.trapz(current, sim_data.time) * 0.9

            delays[i][2] = energy*1e15

            np.savetxt(self.prefix("wordline_driver.csv"), delays, fmt="%10.5g")


WordlineDriverOptimizer.run_tests(__name__)
