#!/usr/bin/env python3

import os, sys

import itertools
from importlib import reload

from char_test_base import CharTestBase


class WordlineEnOptimizer(CharTestBase):
    instantiate_dummy = True

    @staticmethod
    def get_dut_class():
        from modules.precharge_array import precharge_array
        from modules.bitcell_array import bitcell_array
        from base.contact import m2m3
        import characterizer
        reload(characterizer)
        from base.vector import vector
        from base.design import design
        from globals import OPTS

        class dut(design):

            def __init__(self):
                super().__init__("precharge_dut")
                self.num_rows = OPTS.num_rows
                self.num_cols = OPTS.num_cols
                self.precharge_size = OPTS.precharge_size
                self.wire_length = OPTS.wire_length
                self.create_layout()

            def create_layout(self):

                precharge_drivers = precharge_array(self.num_cols, self.precharge_size)
                self.add_mod(precharge_drivers)

                bitcells = bitcell_array(1, self.num_rows)
                self.add_mod(bitcells)

                # add precharge
                precharge_inst = self.add_inst("precharge", precharge_drivers,
                                               offset=vector(0, precharge_drivers.height), mirror="MX")
                args = []
                for i in range(self.num_cols):
                    args.append("bl[{0}]".format(i))
                    args.append("br[{0}]".format(i))
                args.extend(["precharge_en", "vdd"])
                self.connect_inst(args)

                # add bitcells
                y_offset = precharge_inst.uy() + self.wide_m1_space
                x_offset = precharge_inst.rx() + (bitcells.width - precharge_drivers.pc_cell.width)
                bitcell_inst = self.add_inst("bitcells", bitcells, vector(x_offset, y_offset), mirror="MY")

                col = self.num_cols - 1
                args = ["br[{0}]".format(col), "bl[{0}]".format(col)]
                self.add_pin_list(["br[{0}]".format(col), "bl[{0}]".format(col)])
                for row in range(self.num_rows):
                    wl_pin_name = "wl[{0}]".format(row)
                    args.append(wl_pin_name)
                    self.add_pin(wl_pin_name)
                    self.copy_layout_pin(bitcell_inst, wl_pin_name, wl_pin_name)
                args.extend(["vdd", "gnd"])
                self.connect_inst(args)

                self.add_pin_list(["precharge_en", "vdd", "gnd"])

                # connect vdd
                precharge_vdd = precharge_inst.get_pin("vdd")
                bitcell_vdd = min(bitcell_inst.get_pins("vdd"), key=lambda x: x.by())
                self.add_rect("metal1", offset=precharge_vdd.lr(), width=bitcell_vdd.rx()-precharge_vdd.rx(),
                              height=bitcell_vdd.height())
                width = precharge_vdd.height()
                self.add_rect("metal1", offset=vector(bitcell_vdd.rx()-width, precharge_vdd.by()),
                              width=width, height=bitcell_vdd.by()-precharge_vdd.by())

                self.copy_layout_pin(bitcell_inst, "gnd", "gnd")

                # put vdd a few bitcells away from edge
                num_bitcells = 12
                x_offset = precharge_vdd.rx() - num_bitcells*precharge_drivers.pc_cell.width
                self.add_layout_pin_center_rect("vdd", "metal1", offset=vector(x_offset, precharge_vdd.cy()))

                # connect bitlines
                for pin_name in ["bl", "br"]:
                    pin = precharge_inst.get_pin(pin_name+"[{}]".format(self.num_cols-1))
                    self.add_rect(pin.layer, offset=pin.ul(), width=pin.width(), height=bitcell_inst.by()-pin.uy())

                self.copy_layout_pin(bitcell_inst, "bl[0]", "br[{}]".format(self.num_cols-1))
                self.copy_layout_pin(bitcell_inst, "br[0]", "bl[{}]".format(self.num_cols-1))

                # en pin
                en_pin = precharge_inst.get_pin("en")
                self.add_rect(en_pin.layer, offset=en_pin.ul(), height=self.wire_length)
                self.add_layout_pin("precharge_en", en_pin.layer, offset=en_pin.ul()+vector(0, self.wire_length))

        return dut

    def runTest(self):

        from globals import OPTS

        from modules.logic_buffer import LogicBuffer
        from psf_reader import PsfReader
        import numpy as np
        from characterizer import stimuli
        import characterizer
        reload(characterizer)
        from base.design import design

        OPTS.check_lvsdrc = False
        OPTS.wire_length = 50
        OPTS.num_rows = num_rows = 128
        OPTS.num_cols = num_cols = 256
        OPTS.logic_height = 1.4
        OPTS.precharge_size = precharge_size

        thresh = 0.45
        N = 10
        MAX_SIZE = 70
        MIN_SIZE = 2

        self.run_drc_lvs = False

        initial_characterization = False  # one time buffer sizes extraction

        self.stim_file_name = self.prefix("stim.sp")

        end_time = 4

        self.run_lvs = False
        self.run_pex = not initial_characterization

        load_dut = self.get_dut_class()()
        self.load_pex = self.run_pex_extraction(load_dut, "precharge_dut", run_drc=False, run_lvs=False)

        self.run_lvs = False
        self.run_pex = initial_characterization
        self.run_sim = not initial_characterization

        vdd = 0.9

        in_pin_name = "in_driver"

        delays = np.zeros([2*N, 5], np.double)
        # buffer_sizes = np.logspace(0, np.log10(MAX_SIZE), N)
        buffer_sizes = np.linspace(MIN_SIZE, MAX_SIZE, N)
        half_N = int(N/2)

        buffer_sizes = [x for x in itertools.chain(
            *itertools.zip_longest(buffer_sizes[:half_N],
                                   list(reversed(buffer_sizes))[:N-half_N])) if x is not None]

        # chain_lengths = [2, 4]
        chain_lengths = [4, 6]  # 4 measured to have both less energy and delay than 2
        for k in range(len(chain_lengths)):
            chain_length = chain_lengths[k]
            for i in range(N):
                delay_index = k*N + i
                delays[delay_index, 3] = chain_length
                delays[delay_index, 4] = precharge_size

                buffer_size = buffer_sizes[i]

                buffer_stages = [(buffer_size**(1/chain_length))**x for x in range(1, chain_length+1)]
                print(buffer_stages)

                precharge_buffer = LogicBuffer(buffer_stages=buffer_stages, logic="pnand3",
                                               height=OPTS.logic_height)
                # precharge_buffer.name = precharge_buffer.name.replace(".", "_")
                driver_pex = self.run_pex_extraction(precharge_buffer, precharge_buffer.name, run_drc=False,
                                                     run_lvs=self.run_lvs)

                # use one time extracted value, in this example, extraction was done for size=2
                driver_pex = driver_pex.replace("/{}/".format(precharge_size_str.replace(".", "_")), "/2/")

                with open(self.stim_file_name, "w") as stim_file:
                    stim_file.write("simulator lang=spice \n")

                    stim = stimuli(stim_file, corner=self.corner)
                    stim.write_include(self.load_pex)
                    stim_file.write('.include "{}"\n'.format(driver_pex))
                    # stim_file.write('.include "{}"\n'.format(precharge_buffer.name+".sp"))

                    stim_file.write("Xdut {} {} \n".format(" ".join(load_dut.pins), load_dut.name))
                    # driver
                    stim_file.write("Xdriver {0} {0} {0} precharge_en float vdd gnd {1} \n".
                                    format(in_pin_name, precharge_buffer.name))

                    stim.write_supply()

                    stim_file.write("V{} {} gnd PWL ( 0n 0.9v 0.3n 0.9v 0.31n 0v 2n 0v 2.01n 0.9v ) \n"
                                    .format(in_pin_name, in_pin_name))

                    stim_file.write("\nsimulator lang=spectre\n")
                    stim_file.write("simulatorOptions options temp={0} preservenode=all dc_pivot_check=yes"
                                    " \n".format(self.corner[2]))

                    stim_file.write("tran tran step={} stop={}n ic=node  write=spectre.dc \n".format("5p", end_time))

                    pen_row = OPTS.num_rows - 1
                    pen_col = OPTS.num_cols - 1
                    bl_probe = "v(Xdut.N_bl[{}]_Xbitcells_Xbit_r{}_c0_M2_d)".format(pen_col, pen_row)
                    br_probe = "v(Xdut.N_br[{}]_Xbitcells_Xbit_r{}_c0_M1_d)".format(pen_col, pen_row)

                    stim_file.write("saveOptions options save=lvl nestlvl=1 pwr=total \n")


                    stim_file.write("simulator lang=spice \n")

                    stim_file.write(".ic {}=0\n".format(bl_probe))
                    stim_file.write(".ic {}=0\n".format(br_probe))

                    stim_file.write(".probe v(Xdriver.N_logic_out_Xlogic_Mpnand3_nmos1_d) \n")
                    stim_file.write(".probe v(Xdriver.logic_out) \n")
                    stim_file.write(".probe v(Xdut.N_precharge_en_Xprecharge_Xpre_column_{}_Mbl_pmos_g) \n"
                                    .format(pen_col))
                    stim_file.write(".probe v(Xdut.N_precharge_en_Xprecharge_Xpre_column_{}_Mbl_pmos_g) \n"
                                    .format(int(OPTS.num_cols/2)))
                    stim_file.write(".probe {} \n".format(bl_probe))
                    stim_file.write(".probe {} \n".format(br_probe))

                if self.run_sim:
                    stim.run_sim()
                # sim_data = PsfReader("/scratch/ota2/openram/characterization/precharge/2/" + "transient1.tran.tran")
                sim_data = PsfReader(self.prefix("transient1.tran.tran"))
                delay = sim_data.get_delay(in_pin_name,
                                           bl_probe, thresh1=thresh, thresh2=thresh)
                delays[delay_index][0] = buffer_size
                delays[delay_index][1] = delay*1e12

                current = sim_data.get_signal('Vvdd:p')
                energy = -np.trapz(current, sim_data.time) * 0.9

                delays[delay_index][2] = energy*1e15

                np.savetxt(self.prefix("precharge_delays.csv"), delays, fmt="%10.5g")


def analyze():
    import os
    import numpy as np

    from itertools import groupby
    from operator import itemgetter

    from matplotlib.pylab import plt

    sim_dir = os.path.join(os.environ["SCRATCH"], "openram", "characterization", "precharge")

    directories = [os.path.join(sim_dir, d) for d in os.listdir(sim_dir)
                   if os.path.isdir(os.path.join(sim_dir, d))]

    size_key = 4
    stages_key = 3
    buffer_size_key = 0

    data = None

    for directory in directories:
        data_file = os.path.join(directory, "precharge_delays.csv")
        if os.path.isfile(data_file):
            new_data = np.loadtxt(data_file)
            if data is None:
                data = new_data
            else:
                data = np.concatenate((data, new_data))

    # groupby needs sorting
    data = np.array(sorted(data, key=lambda x: x[stages_key]))
    data = data.tolist()

    i = 1

    stages_dict = {}

    for num_stages, stage_data in groupby(data, key=lambda x: str(int(x[stages_key]))):
        plt.figure(i)
        i += 1
        stage_data = list(sorted(stage_data, key=itemgetter(size_key)))
        stages_dict[num_stages] = np.array(stage_data)
        grouped_dict = {}
        for key, val in groupby(stage_data, key=itemgetter(size_key)):
            grouped_dict[key] = list(val)
        all_sizes = list(sorted(grouped_dict.keys()))
        for precharge_size in all_sizes:
            m = np.array(list(grouped_dict[precharge_size]))
            plt.scatter(m[1:, 1], m[1:, 2], label="{:.2g}".format(precharge_size))

            for i in range(1, len(m)):
                plt.text(m[i, 1] + 2, m[i, 2],
                         str(int(m[i, 0])), fontsize=3.5)

        plt.legend()
        plt.title("num_stages = {}".format(num_stages))
        plt.show(block=False)

    N = 10
    np.set_printoptions(linewidth=140)
    for i in range(int(len(stages_dict['4']) / N)):
        four_data = np.array(sorted(stages_dict['4'][i * N:(i + 1) * N], key=itemgetter(buffer_size_key)))
        six_data = np.array(sorted(stages_dict['6'][i * N:(i + 1) * N], key=itemgetter(buffer_size_key)))
        precharge_size = four_data[0][size_key]
        print("precharge = {}: ".format(precharge_size))
        differences = (four_data[:, 1:3] - six_data[:, 1:3])
        differences = np.append(differences, four_data[:, 1])
        differences = np.append(differences, four_data[:, buffer_size_key])

        differences = differences.reshape([4, N])

        print(np.array(differences))


if "analyze" in sys.argv:
    analyze()
else:
    size_index = sys.argv.index("size") + 1
    precharge_size_str = sys.argv[size_index]
    precharge_size = float(precharge_size_str)

    openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "characterization")
    sim_dir = "{}/precharge/{}".format(openram_temp, precharge_size_str.replace(".", "_"))
    WordlineEnOptimizer.temp_folder = sim_dir

    sys.argv = sys.argv[:size_index-1]
    WordlineEnOptimizer.run_tests(__name__)