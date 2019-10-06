import os
import shutil
from importlib import reload

import characterizer
from base.design import design
from base.vector import vector
from characterizer import stimuli
from characterizer.sequential_delay import SequentialDelay
from globals import OPTS
from modules.bitline_compute.bitline_adder import BitlineAdder
from pgates.pinv import pinv


class SigBuffer(design):

    def __init__(self, size):
        super().__init__("sig_buffer_{}".format(size))
        self.add_pin_list("vin vout vdd gnd".split())

        inv = pinv(size=size)
        self.add_mod(inv)

        self.add_inst("in_inv", inv, offset=vector(0, 0))
        self.connect_inst("vin vin_bar vdd gnd".split())
        self.add_inst("in_buf", inv, offset=vector(0, 0))
        self.connect_inst("vin_bar vout vdd gnd".split())


class SpiceGenerator(SequentialDelay):
    trim_sp_file = None
    sim_sp_file = None
    sf = None
    stim = None
    cload = "0"

    def __init__(self, spfile, corner, adder, buffer, buffer_large):
        self.sp_file = spfile
        self.corner = corner
        self.adder = adder  # type: -> BitlineAdder
        self.buffer = buffer  # type: -> SigBuffer
        self.buffer_large = buffer_large  # type: -> SigBuffer
        self.num_cols = self.adder.num_cols
        self.word_size = self.adder.word_size
        self.num_words = self.adder.num_words

        self.vdd_voltage = corner[1]

        self.sel_sigs = ["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor", "s_sum"]

    def prepare_netlist(self):
        """ Prepare a trimmed netlist and regular netlist. """

        # Set up to trim the netlist here if that is enabled
        if OPTS.use_pex:
            self.trim_sp_file = OPTS.pex_spice
        else:
            # The non-reduced netlist file when it is disabled
            self.trim_sp_file = os.path.join(OPTS.openram_temp, "adder.sp")

        # The non-reduced netlist file for power simulation
        self.sim_sp_file = os.path.join(OPTS.openram_temp, "adder.sp")
        # Make a copy in temp for debugging
        shutil.copy(self.sp_file, self.sim_sp_file)

    def instantiate_adder(self):
        self.sf.write("Xadder ")

        for col in range(self.num_cols):
            self.sf.write("and_in[{}] ".format(col))
            self.sf.write("nor_in[{}] ".format(col))

        for col in range(self.num_cols):
            self.sf.write("bus_out[{}] ".format(col))

        for word in range(self.num_words):
            self.sf.write(" cin[{0}] cout[{0}] ".format(word))

        self.sf.write(" s_and s_nand s_or s_nor s_xor s_xnor s_sum ")
        self.sf.write(" clk vdd gnd {} \n".format(self.adder.name))

    def instantiate_buffered_dc(self, value, signal_name):
        generated_sig_name = signal_name+"_source"
        self.stim.gen_constant(generated_sig_name, value, gnd_node="gnd")
        self.sf.write("Xbuf_{} {} {} vdd gnd {} \n\n".format(signal_name, generated_sig_name, signal_name,
                                                             self.buffer.name))

    def instantiate_buffered_transition(self, value, signal_name, delay, buffer_name=None):
        if buffer_name is None:
            buffer_name = self.buffer.name

        value = bool(int(value))
        final_voltage = value * self.vdd_voltage
        initial_voltage = (not value) * self.vdd_voltage
        self.sf.write("V{signal_name}_source {signal_name}_source gnd PULSE({initial_voltage}, "
                      "{final_voltage}, {delay}n "
                      "{rise_time} {rise_time}) \n"
                      .format(signal_name=signal_name, initial_voltage=initial_voltage,
                              final_voltage=final_voltage, delay=delay, rise_time="10p"))

        self.sf.write("Xbuf_{signal_name} {signal_name}_source {signal_name} vdd gnd {buffer_name} \n\n"
                      .format(signal_name=signal_name, buffer_name=buffer_name))

    def instantiate_bus_selects(self, selected_sig):
        for sig in self.sel_sigs:
            if sig == selected_sig:
                v = self.vdd_voltage
            else:
                v = 0
            self.instantiate_buffered_dc(v, sig)

    def instantiate_load(self, signal_name):
        self.sf.write("C{} {} gnd {} \n".format(signal_name, signal_name, self.cload))

    def generate_spice(self, selected_sig, cins, and_in, nor_in, clk_delay, cload,
                       sim_length):
        # clk_delay in nanoseconds
        reload(characterizer)

        vdd_voltage = self.vdd_voltage
        self.cload = cload

        self.current_time = 0
        temp_stim = os.path.join(OPTS.openram_temp, "stim.sp")

        with open(temp_stim, "w") as sf:
            self.sf = sf

            stim = stimuli(stim_file=sf, corner=self.corner)
            self.stim = stim

            if OPTS.spice_name == "spectre":
                sf.write("simulator lang=spice\n")

            sf.write("*Bitline Adder standalone simulation \n")

            stim.write_include(self.trim_sp_file)

            self.instantiate_adder()
            self.instantiate_bus_selects(selected_sig)

            # clk : rise after clk_delay

            self.sf.write("\n*** clk *** \n\n")
            self.instantiate_buffered_transition(1, "clk", clk_delay, buffer_name=self.buffer_large.name)

            cins = list(reversed(cins))
            for word in range(self.num_words):
                self.instantiate_buffered_dc(vdd_voltage*cins[word], "cin[{}]".format(word))

            self.sf.write("\n*** vdd gnd *** \n\n")
            self.stim.gen_constant("vdd", vdd_voltage, gnd_node="gnd")
            self.stim.gen_constant("gnd", 0, gnd_node="0")

            self.sf.write("\n*** and nor inputs *** \n\n")

            input_delay = 0.5*clk_delay

            and_in = list(reversed(and_in))
            nor_in = list(reversed(nor_in))
            for col in range(self.num_cols):
                self.instantiate_buffered_transition(and_in[col], "and_in[{}]".format(col), input_delay)
                self.instantiate_buffered_transition(nor_in[col], "nor_in[{}]".format(col), input_delay)

            self.sf.write("\n*** loads *** \n\n")

            for col in range(self.num_cols):
                self.instantiate_load("bus_out[{}]".format(col))
            for word in range(self.num_words):
                self.instantiate_load("cout[{}]".format(word))

            self.stim.write_control(sim_length)
