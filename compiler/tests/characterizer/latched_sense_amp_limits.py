#!/usr/bin/env python3
import itertools
from importlib import reload

from char_test_base import CharTestBase


class LatchedSenseAmp(CharTestBase):
    instantiate_dummy = True

    def runTest(self):
        from globals import OPTS
        import sys
        sys.path.append("../../modules/bitline_compute")

        from modules.bitline_compute.dual_latched_sense_amp_array import dual_latched_sense_amp_array
        from modules.buffer_stage import BufferStage
        from psf_reader import PsfReader
        import numpy as np
        from characterizer import stimuli
        import characterizer
        reload(characterizer)
        from base.vector import vector
        from base.contact import m1m2, m2m3
        from base.design import design

        OPTS.sense_amp_array = "dual_latched_sense_amp_array"
        OPTS.sense_amp_tap = "dual_latched_sense_amp_tap"
        OPTS.sense_amp = "dual_latched_sense_amp"

        class dut(design):
            def __init__(self, buffer_size, probe_pin="sampleb"):
                # name = "sense_amp_dut_" + "%.3g".format(buffer_size).replace(".", "_")
                super().__init__("sense_amp_dut")
                self.num_cols = OPTS.num_cols
                self.wire_length = OPTS.wire_length
                self.buffer_size = buffer_size
                self.probe_pin = probe_pin
                self.create_layout()

            def create_layout(self):

                self.buffer = BufferStage([buffer_size], height=1.4)
                self.add_mod(self.buffer)

                self.amp_array = dual_latched_sense_amp_array(word_size=self.num_cols, words_per_row=1)
                self.add_mod(self.amp_array)

                combined_pins = ["diff", "diffb", "sampleb", "search_ref"]

                probe_pin = min(self.amp_array.get_pins(self.probe_pin), key=lambda x: x.by())

                in_pin_name = "in_" + self.probe_pin

                y_offset = probe_pin.cy() + 0.5*self.buffer.height
                self.buffer_inst = self.add_inst("buffer", self.buffer, offset=vector(0, y_offset), mirror="MX")
                self.connect_inst([in_pin_name, self.probe_pin, "float", "vdd_buf", "gnd"])
                self.copy_layout_pin(self.buffer_inst, "vdd", "vdd_buf")
                self.copy_layout_pin(self.buffer_inst, "gnd", "gnd")
                self.copy_layout_pin(self.buffer_inst, "in", in_pin_name)

                for pin_name in [in_pin_name, "vdd_buf"]:
                    self.add_pin(pin_name)

                x_offset = self.buffer_inst.rx() + self.wide_m1_space + OPTS.wire_length

                pin_x = self.buffer_inst.rx() + self.wide_m1_space
                self.add_rect(probe_pin.layer, offset=vector(self.buffer_inst.get_pin("out_inv").rx(), probe_pin.by()),
                              width=x_offset-self.buffer_inst.get_pin("out_inv").rx(), height=probe_pin.height())

                offset = vector(x_offset, 0)
                self.array_inst = array = self.add_inst("array", self.amp_array, offset=offset)

                col_pins = ["bl", "br", "and", "nor"]
                other_pins = ["en", "preb", "sampleb", "diff", "diffb", "search_ref", "vdd", "gnd"]

                args = []

                for col in range(self.num_cols):
                    for pin_name in col_pins:
                        name = pin_name + "[{}]".format(col)
                        self.add_pin(name)
                        self.copy_layout_pin(array, name, name)
                        args.append(name)

                for pin_name in other_pins:
                    self.add_pin(pin_name)
                    args.append(pin_name)
                    if pin_name not in combined_pins:
                        self.copy_layout_pin(array, pin_name, pin_name)

                self.connect_inst(args)

                pitch = m1m2.second_layer_height + self.line_end_space
                x_offset = array.lx() - pitch - self.line_end_space
                for pin_name in combined_pins:
                    bottom, top = sorted(array.get_pins(pin_name), key=lambda x: x.by())
                    self.add_layout_pin(pin_name, bottom.layer, offset=vector(pin_x, bottom.by()),
                                        width=bottom.lx()-pin_x, height=bottom.height())

                    self.add_rect("metal2", offset=vector(x_offset, bottom.by()), height=top.uy() - bottom.by())
                    for pin in [top, bottom]:
                        self.add_rect(pin.layer, offset=vector(x_offset, pin.by()),
                                      width=pin.lx() - x_offset, height=pin.height())
                        if pin.layer == "metal1":
                            contact = m1m2
                        else:
                            contact = m2m3
                        self.add_contact_center(contact.layer_stack,
                                                offset=vector(x_offset+0.5*self.m2_width, pin.cy()),
                                                rotate=90)
                    x_offset -= pitch

                # connect gnd pins
                buffer_gnd = self.buffer_inst.get_pin("gnd")
                load_gnd = max(self.array_inst.get_pins("gnd"), key=lambda x: x.by())
                self.add_rect("metal1", offset=vector(buffer_gnd.rx(), load_gnd.by()),
                              width=load_gnd.lx()-buffer_gnd.rx(), height=load_gnd.height())
                self.add_rect("metal1", offset=vector(buffer_gnd.rx(), buffer_gnd.by()),
                              width=load_gnd.height(), height=load_gnd.uy()-buffer_gnd.by())

        OPTS.check_lvsdrc = False
        OPTS.wire_length = 30
        OPTS.num_cols = 256

        thresh = 0.45
        N = 20
        MAX_SIZE = 100

        self.run_drc_lvs = False

        self.stim_file_name = self.prefix("stim.sp")

        self.run_pex = True
        self.run_sim = True

        end_time = 4

        probe_nets = {
            "sampleb": "N_sampleb_Xarray_Xsa_d{}_MM0_g",
            "en": "N_en_Xarray_Xsa_d{}_XI2_MM2_g"
        }

        vdd = 0.9
        r_driver = 500

        dc_voltages = {
            "diff": 0,
            "diffb": vdd,
            "search_ref": 0.75,
            "preb": vdd,
            "en": 0,
            "vdd_buf": vdd,
        }

        probe_pin_name = "sampleb"
        in_pin_name = "in_" + probe_pin_name

        delays = np.ndarray([N, 3], np.double)
        # buffer_sizes = np.logspace(0, np.log10(MAX_SIZE), N)
        buffer_sizes = np.linspace(1, MAX_SIZE, N)
        half_N = int(N/2)

        buffer_sizes = [x for x in itertools.chain(
            *itertools.zip_longest(buffer_sizes[:half_N],
                                   list(reversed(buffer_sizes))[:N-half_N])) if x is not None]

        for i in range(N):
            buffer_size = buffer_sizes[i]
            design.name_map = []
            load = dut(buffer_size)

            self.load_pex = self.run_pex_extraction(load, "dual_sense_amp_dut", run_drc=False, run_lvs=False)
            self.dut_name = load.name

            with open(self.stim_file_name, "w") as stim_file:
                stim_file.write("simulator lang=spice \n")

                stim = stimuli(stim_file, corner=self.corner)
                stim.write_include(self.load_pex)

                stim_file.write("Xdut {} sense_amp_dut \n".format(
                    " ".join(load.pins)))
                stim.write_supply()

                stim_file.write("V{} {} gnd PWL ( 0n 0.9v 0.3n 0.9v 0.31n 0v 2n 0v 2.01n 0.9v ) \n"
                                .format(in_pin_name, in_pin_name))
                # stim_file.write("R1 sampleb_1 sampleb {} \n".format(r_driver))

                for net in dc_voltages:
                    stim_file.write("V{} {} 0 {}\n".format(net, net, dc_voltages[net]))

                for net in probe_nets:
                    stim_file.write(".probe v({}) \n".format(net))
                    for col in range(OPTS.num_cols):
                        stim_file.write(".probe v(Xdut.{}) \n".format(probe_nets[net].format(col)))

                stim_file.write("\nsimulator lang=spectre\n")
                stim_file.write("simulatorOptions options temp={0} preservenode=all dc_pivot_check=yes"
                                " \n".format(self.corner[2]))

                stim_file.write("tran tran step={} stop={}n ic=node write=spectre.dc \n".format("5p", end_time))

                stim_file.write("saveOptions options save=lvlpub nestlvl=1 pwr=total \n")
                stim_file.write("simulator lang=spice \n")

            if self.run_sim:
                stim.run_sim()
            sim_data = PsfReader(self.prefix("transient1.tran.tran"))
            delay = sim_data.get_delay(in_pin_name,
                                       "v(Xdut.N_sampleb_Xarray_Xsa_d255_MM0_g)", thresh1=thresh, thresh2=thresh)
            delays[i][0] = buffer_size
            delays[i][1] = delay*1e12

            current = sim_data.get_signal('Vvdd:p') + sim_data.get_signal('Vvdd_buf:p')
            energy = -np.trapz(current, sim_data.time) * 0.9

            delays[i][2] = energy*1e15

            np.savetxt(self.prefix("buffers.csv"), delays, fmt="%10.5g")


LatchedSenseAmp.run_tests(__name__)
