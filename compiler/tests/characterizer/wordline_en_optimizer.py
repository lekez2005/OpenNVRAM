#!/usr/bin/env python3
import itertools
from importlib import reload

from char_test_base import CharTestBase


class WordlineEnOptimizer(CharTestBase):
    instantiate_dummy = True

    @staticmethod
    def make_wordline_driver():
        from modules.wordline_driver_array import wordline_driver_array
        from modules.hierarchical_decoder import hierarchical_decoder
        from base.contact import m2m3
        import characterizer
        reload(characterizer)
        from base.vector import vector
        from base.design import design
        from globals import OPTS

        class dut(design):

            def __init__(self):
                super().__init__("wordline_en_dut")
                self.num_rows = OPTS.num_rows
                self.wire_length = OPTS.wire_length
                self.create_layout()

            def create_layout(self):

                y_offset = OPTS.wire_length

                # decoder
                decoder = hierarchical_decoder(self.num_rows)
                self.add_mod(decoder)

                decoder_inst = self.add_inst("decoder", decoder,
                                             vector(0, y_offset-(decoder.height-decoder.row_decoder_height)))

                args = []
                for j in range(decoder.num_inputs):
                    args.append("A[{0}]".format(j))

                for j in range(decoder.rows):
                    args.append("decode[{0}]".format(j))
                if decoder.use_flops:
                    args.append("clk")
                args.append("vdd")
                args.append("gnd")

                self.connect_inst(args)

                buffer_stages = getattr(OPTS, "wordline_buffers", [1, 4, 16])
                self.array = wordline_driver_array(self.num_rows, buffer_stages)
                self.add_mod(self.array)

                x_offset = decoder_inst.rx() - (decoder.width-decoder.row_decoder_width)

                self.array_inst = self.add_inst("driver_array", self.array, vector(x_offset, y_offset))

                # inputs to wordline_driver.
                args = []
                for i in range(self.num_rows):
                    pin_name = "in[{0}]".format(i)
                    self.add_pin(pin_name)
                    self.copy_layout_pin(self.array_inst, pin_name)
                    args.append(pin_name)

                # Outputs from wordline_driver.
                for i in range(self.num_rows):
                    pin_name = "wl[{0}]".format(i)
                    self.add_pin(pin_name)
                    self.copy_layout_pin(self.array_inst, pin_name)
                    args.append(pin_name)

                self.add_pin("en")
                args.append("en")

                for pin_name in ["vdd", "gnd"]:
                    self.add_pin(pin_name)
                    self.copy_layout_pin(self.array_inst, pin_name)
                    args.append(pin_name)

                self.connect_inst(args)

                # en pin
                en_pin = self.array_inst.get_pin("en")
                self.add_contact(m2m3.layer_stack, offset=en_pin.ll())
                x_offset = self.array_inst.rx() + self.wide_m1_space + self.rail_height + self.parallel_line_space
                self.add_rect("metal3", offset=en_pin.ll(), width=x_offset-en_pin.lx())
                self.add_contact(m2m3.layer_stack, offset=vector(x_offset, en_pin.by()))
                self.add_layout_pin("en", en_pin.layer, vector(x_offset, 0),
                                    width=en_pin.width(), height=en_pin.by())

                # vdd and gnd pins
                offsets = [decoder_inst.lx() - self.wide_m1_space - self.rail_height,
                           self.array_inst.rx() + self.wide_m1_space]
                names = ["vdd", "gnd"]
                for i in range(2):
                    pin_name = names[i]
                    self.add_layout_pin(pin_name, "metal1", offset=vector(offsets[i], decoder_inst.by()),
                                        height=decoder_inst.height)
                    for pin in decoder_inst.get_pins(pin_name):
                        self.add_rect("metal1", offset=vector(offsets[i], pin.by()),
                                      width=pin.cx()-offsets[i] + self.rail_height, height=pin.height())

                # join nwells
                well_height = 0.4*decoder.nand_inst[0].mod.height
                for pin in self.array_inst.get_pins("vdd"):
                    self.add_rect("nwell", offset=vector(decoder_inst.rx(), pin.cy()-well_height),
                                  height=well_height, width=self.array_inst.lx()-decoder_inst.rx())

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
        OPTS.wire_length = 35
        OPTS.num_rows = num_rows = 128
        OPTS.logic_height = 1.4

        thresh = 0.45
        N = 20
        MAX_SIZE = 100

        self.run_drc_lvs = False

        self.stim_file_name = self.prefix("stim.sp")

        end_time = 4

        self.run_lvs = True
        self.run_pex = False

        load_dut = self.make_wordline_driver()
        self.load_pex = self.run_pex_extraction(load_dut, "wordline_en_dut", run_drc=False, run_lvs=False)

        self.run_lvs = False
        self.run_pex = True
        self.run_sim = True

        vdd = 0.9

        in_pin_name = "in_driver"

        delays = np.zeros([N, 3], np.double)
        # buffer_sizes = np.logspace(0, np.log10(MAX_SIZE), N)
        buffer_sizes = np.linspace(2, MAX_SIZE, N)
        half_N = int(N/2)

        buffer_sizes = [x for x in itertools.chain(
            *itertools.zip_longest(buffer_sizes[:half_N],
                                   list(reversed(buffer_sizes))[:N-half_N])) if x is not None]

        for i in range(N):
            buffer_size = buffer_sizes[i]

            buffer_stages = [(buffer_size**(1/3))**x for x in range(4)]
            print(buffer_stages)

            wordline_buf = LogicBuffer(buffer_stages=buffer_stages, logic="pnor2",
                                       height=OPTS.logic_height)

            design.name_map = []
            driver_pex = self.run_pex_extraction(wordline_buf, "wl_en_driver", run_drc=False, run_lvs=self.run_lvs)

            with open(self.stim_file_name, "w") as stim_file:
                stim_file.write("simulator lang=spice \n")

                stim = stimuli(stim_file, corner=self.corner)
                stim.write_include(self.load_pex)
                stim_file.write('.include "{}"\n'.format(driver_pex))

                stim_file.write("Xdut {} {} \n".format(" ".join(load_dut.pins), load_dut.name))
                stim.write_supply()

                stim_file.write("V{} {} gnd PWL ( 0n 0.9v 0.3n 0.9v 0.31n 0v 2n 0v 2.01n 0.9v ) \n"
                                .format(in_pin_name, in_pin_name))
                # stim_file.write("R1 sampleb_1 sampleb {} \n".format(r_driver))
                for j in range(OPTS.num_rows-1):
                    in_name = "in[{}]".format(j)
                    stim_file.write("V{} {} 0 0\n".format(in_name, in_name))

                stim_file.write("Vin[{}] in[{}] 0 {}\n".format(num_rows-1, num_rows-1, vdd))

                # driver
                stim_file.write("Xdriver gnd {} float en vdd gnd {} \n".format(in_pin_name, wordline_buf.name))

                stim_file.write("\nsimulator lang=spectre\n")
                stim_file.write("simulatorOptions options temp={0} preservenode=all dc_pivot_check=yes"
                                " \n".format(self.corner[2]))

                stim_file.write("tran tran step={} stop={}n ic=node write=spectre.dc \n".format("5p", end_time))

                stim_file.write("saveOptions options save=lvl nestlvl=1 pwr=total \n")
                stim_file.write("simulator lang=spice \n")

                for j in range(num_rows):
                    stim_file.write(".probe v(wl[{}]) \n".format(j))

            if self.run_sim:
                stim.run_sim()
            sim_data = PsfReader(self.prefix("transient1.tran.tran"))
            delay = sim_data.get_delay(in_pin_name,
                                       "wl[{}]".format(OPTS.num_rows-1), thresh1=thresh, thresh2=thresh)
            delays[i][0] = buffer_size
            delays[i][1] = delay*1e12

            current = sim_data.get_signal('Vvdd:p')
            energy = -np.trapz(current, sim_data.time) * 0.9

            delays[i][2] = energy*1e15

            np.savetxt(self.prefix("wordline_en.csv"), delays, fmt="%10.5g")


WordlineEnOptimizer.run_tests(__name__)
