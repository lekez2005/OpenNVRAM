import numpy as np


import delay
import debug
from globals import OPTS
import stimuli
import tech


class SequentialDelay(delay.delay):
    """
    Class to set up measurements for simulation and process results after simulation
    Extends the delay class to provide functionality for testing multiple addresses
    """

    def __init__(self, sram, spfile, corner):

        delay.delay.__init__(self, sram, spfile, corner)

        self.period = float(tech.spice["feasible_period"])
        self.setup_time = float(2*tech.spice["msflop_setup"])*1e-3
        self.slew = float(2*tech.spice["rise_time"])

        self.gmin = 1e-13  # put gmin resistor at probe points to prevent Cadence from removing them as dangling nodes

        self.current_time = 0

        self.oeb = self.prev_oeb = 1
        self.acc_en = self.prev_acc_en = self.web = self.prev_web = 0
        self.acc_en_inv = self.prev_acc_en_inv = 1
        self.csb = self.prev_csb = 0
        self.address = self.prev_address = [0]*self.addr_size
        self.data = self.prev_data = [0]*self.word_size

        self.control_sigs = ["oeb", "web", "acc_en", "acc_en_inv", "csb"]
        self.bus_sigs = []
        for i in range(self.addr_size):
            self.bus_sigs.append("A[{}]".format(i))
        for i in range(self.word_size):
            self.bus_sigs.append("data[{}]".format(i))


        self.v_data = {}  # saves PWL command for each voltage source
        self.v_comments = {}
        self.q_address_pins = {} # for each address to be probed, contains list of Q pins
        self.probe_points = []
        self.probes_dict = {}
        self.saved_nodes = set()
        self.measure_commands = []
        self.command_comments = []

        self.initialize_output()

    def set_stimulus_params(self, addresses, saved_nodes=None, reset_address=1):
        """Set address and nodes to be saved"""
        if saved_nodes is None:
            saved_nodes = []
        self.saved_nodes = set(saved_nodes)
        self.addresses = addresses
        self.reset_address = reset_address


    def write_delay_stimulus(self):
        """ Override super class method to use internal logic for pwl voltages and measurement setup
        Assumes set_stimulus_params has been called to define the addresses and nodes
         Creates a stimulus file for simulations to probe a bitcell at a given clock period.
        Address and bit were previously set with set_stimulus_params().
        """

        # creates and opens stimulus file for writing
        self.current_time = 0
        temp_stim = "{0}/stim.sp".format(OPTS.openram_temp)
        self.sf = open(temp_stim, "w")
        if OPTS.spice_name == "spectre":
            self.sf.write("simulator lang=spice\n")
        self.sf.write("* Delay stimulus for period of {0}n load={1}fF slew={2}ns\n\n".format(self.period,
                                                                                             self.load,
                                                                                             self.slew))
        self.stim = stimuli.stimuli(self.sf, self.corner)
        # include files in stimulus file
        self.stim.write_include(self.trim_sp_file)

        self.write_generic_stimulus()

        ones = (2 ** self.word_size) - 1

        self.initialize_output()

        reset_address_vec = self.convert_address(self.reset_address)

        for addr_dict in self.addresses:
            address = self.convert_address(addr_dict["address"])
            address_int = self.address_to_int(address)
            address_labels = addr_dict["net_names"]

            self.write_data(address, ones)

            self.setup_write_delay(address_int, address_labels, "HL")
            self.write_data(address, 0)
            self.write_data(reset_address_vec, ones, "set data bus high so we can observe transition")
            self.setup_read_delay(address_int, "HL")
            self.read_data(address)

            self.setup_write_delay(address_int, address_labels, "LH")
            self.write_data(address, ones)
            self.write_data(reset_address_vec, 0, "set data bus low so we can observe transition")
            self.setup_read_delay(address_int, "LH")
            self.read_data(address)

        for node in self.saved_nodes:
            self.sf.write(".plot V({0}) \n".format(node))

        self.finalize_output()


        self.sf.write("\n* Generation of global clock signal\n")
        self.stim.gen_pulse(sig_name="CLK",
                            v1=0,
                            v2=self.vdd_voltage,
                            offset=self.period,
                            period=self.period,
                            t_rise=self.slew,
                            t_fall=self.slew)


        # run until the end of the cycle time
        self.stim.write_control(self.current_time + self.period)

        self.sf.close()

    def write_generic_stimulus(self):
        """ Overrides super class method to use internal logic for measurement setup
        Create the sram instance, supplies, loads, and access transistors. """

        # add vdd/gnd statements
        self.sf.write("\n* Global Power Supplies\n")
        self.stim.write_supply()

        # instantiate the sram
        self.sf.write("\n* Instantiation of the SRAM\n")
        self.stim.inst_sram(abits=self.addr_size,
                            dbits=self.word_size,
                            sram_name=self.name)

        self.sf.write("\n* SRAM output loads\n")
        for i in range(self.word_size):
            self.sf.write("CD{0} d[{0}] 0 {1}f\n".format(i, self.load))

        # add access transistors for data-bus
        self.sf.write("\n* Transmission Gates for data-bus and control signals\n")
        self.stim.inst_accesstx(dbits=self.word_size)


    def initialize_output(self):
        """initialize pwl signals"""

        self.oeb = self.prev_oeb = 1
        self.acc_en = self.prev_acc_en = self.web = self.prev_web = 0
        self.acc_en_inv = self.prev_acc_en_inv = 1
        self.csb = self.prev_csb = 0
        self.address = self.prev_address = [0] * self.addr_size
        self.data = self.prev_data = [0] * self.word_size

        for key in self.control_sigs:
            curr_val = getattr(self, key)
            self.v_data[key] = "V{0} {0} 0 PWL ( 0, {1}v, ".format(key, curr_val*self.vdd_voltage)
            self.v_comments[key] = "* (time, data): [ (0, {}), ".format(curr_val)

        for key in self.bus_sigs:
            self.v_data[key] = "V{0} {0} 0 PWL ( 0, {1}v, ".format(key, 0)
            self.v_comments[key] = "* (time, data): [ (0, 0), "

        self.current_time += self.period

    def finalize_output(self):
        """Complete pwl statements"""
        self.sf.write("\n* Command comments\n")
        for comment in self.command_comments:
            self.sf.write(comment)
        self.sf.write("\n* Generation of control signals\n")
        for key in sorted(self.control_sigs):
            self.sf.write(self.v_comments[key][:-1] + " ] \n")
            self.sf.write(self.v_data[key] + " )\n")
        self.sf.write("\n* Generation of data and address signals\n")
        for key in sorted(self.bus_sigs):
            self.sf.write(self.v_comments[key][:-1] + " ] \n")
            self.sf.write(self.v_data[key] + " )\n")


    def write_pwl(self, key, prev_val, curr_val):
        """Append current time's data to pwl. Transitions from the previous value to the new value using the slew"""
        if key in ["acc_en", "acc_en_inv"]:
            setup_time = 0
        else:
            setup_time = self.setup_time
        t1 = max(0.0, self.current_time - 0.5 * self.slew - setup_time)
        t2 = max(0.0, self.current_time + 0.5 * self.slew - setup_time)
        self.v_data[key] += " {0}n {1}v {2}n {3}v ".format(t1, self.vdd_voltage*prev_val, t2, self.vdd_voltage*curr_val)
        self.v_comments[key] += " ({0}, {1}) ".format(int(self.current_time/self.period),
                                                      curr_val)

    def write_pwl_from_key(self, key):
        curr_val = getattr(self, key)
        prev_val = getattr(self, "prev_" + key)
        self.write_pwl(key, prev_val, curr_val)
        setattr(self, "prev_" + key, curr_val)


    def update_output(self):
        """Generate voltage at current time for each pwl voltage supply"""
        # control signals
        for key in self.control_sigs:
            self.write_pwl_from_key(key)

        # write address
        for i in range(self.addr_size):
            key = "A[{}]".format(i)
            self.write_pwl(key, self.prev_address[i], self.address[i])
        self.prev_address = self.address

        # write data
        for i in range(self.word_size):
            key = "data[{}]".format(i)
            self.write_pwl(key, self.prev_data[i], self.data[i])
        self.prev_data = self.data



    def write_data(self, address_vec, data, comment=""):
        """Write data to an address. Data can be integer or binary vector. Address is binary vector"""
        self.address = address_vec
        self.data = self.convert_data(data)
        self.command_comments.append("* t = {} Write {} to {} {} \n".format(self.current_time, self.data,
                                                                            self.address, comment))
        self.acc_en = self.web = 0
        self.acc_en_inv = 1
        self.oeb = 1
        self.csb = 0
        self.update_output()
        self.current_time += self.period

    def read_data(self, address_vec, comment=""):
        """Read from an address. Address is a binary vector"""
        # self.measure_write(address, data)
        self.address = address_vec
        self.command_comments.append("* t = {} Read {} {} \n".format(self.current_time, address_vec, comment))
        self.acc_en = self.web = 1
        self.acc_en_inv = 0
        self.oeb = 0
        self.csb = 0
        self.update_output()
        # self.current_time += 2*self.period
        self.current_time += self.period

    def convert_address(self, address):
        """Convert address integer or vector to binary list MSB first"""
        if type(address) == int:
            return list(map(int, np.binary_repr(address, width=self.addr_size)))
        elif type(address) == list and len(address) == self.addr_size:
            return address
        else:
            debug.error("Invalid address: {}".format(address), -1)

    def address_to_int(self, address):
        """Convert address to integer. Address can be vector of integers MSB first or integer"""
        if type(address) == int:
            return address
        elif type(address) == list:
            return int("".join(str(a) for a in address), base=2)
        else:
            debug.error("Invalid data: {}".format(address), -1)

    def convert_data(self, data):
        """Convert data integer to binary list MSB first"""
        if type(data) == int:
            return list(map(int, np.binary_repr(data, self.word_size)))
        elif type(data) == list and len(data) == self.word_size:
            return data
        else:
            debug.error("Invalid data: {}".format(data), -1)

    def setup_delay_measurement(self, transition, net, delay_name, slew_name):
        """Write measurement command. Transition is HL or LH.
        delay name is name to be used the delay measurement
        slew_name is name to be used for slew measurement
        """
        if transition == "LH":
            targ_dir = "RISE"
            prev_val = 0.1 * self.vdd_voltage
            final_val = 0.9 * self.vdd_voltage
        elif transition == "HL":
            targ_dir = "FALL"
            prev_val = 0.9 * self.vdd_voltage
            final_val = 0.1 * self.vdd_voltage
        else:
            debug.error("Invalid transition direction {} specified".format(transition), -1)
            return
        trig_val = targ_val = 0.5 * self.vdd_voltage
        self.stim.gen_meas_delay(meas_name=delay_name,
                                 trig_name="clk", trig_val=trig_val, trig_dir="FALL",
                                 trig_td=self.current_time,
                                 targ_name=net, targ_val=targ_val, targ_dir=targ_dir,
                                 targ_td=self.current_time + 0.5 * self.period)
        self.stim.gen_meas_delay(meas_name=slew_name,
                                 trig_name=net, trig_val=prev_val, trig_dir="FALL",
                                 trig_td=self.current_time + 0.5 * self.period,
                                 targ_name=net, targ_val=final_val, targ_dir=targ_dir,
                                 targ_td=self.current_time + 0.5 * self.period)

    def setup_power_measurement(self, action, transition, address_int):
        """Write Power measurement command
        action is READ or WRITE, transition is HL or LH
        """
        if transition == "LH":
            value = 1
        else:
            value = 0
        meas_name = "{}{}_POWER_a{}".format(action, value, address_int)
        self.stim.gen_meas_power(meas_name=meas_name,
                                 t_initial=self.current_time - self.setup_time,
                                 t_final=self.current_time + self.period - self.setup_time)


    def setup_read_delay(self, address_int, transition):
        """Set up read delay measurement for each bit in address.
        Transition is HL or LH.
        Should be called before the read command
        """
        self.setup_power_measurement("READ", transition, address_int)
        for i in range(self.word_size):

            net = "D[{}]".format(i)
            self.setup_delay_measurement(transition, net,
                                   delay_name="R_DELAY_{}_a{}_d{}".format(transition, address_int, i),
                                   slew_name="R_SLEW_{}_a{}_d{}".format(transition, address_int, i))

    def setup_write_delay(self, address_int, address_labels, transition):
        """Set up write delay measurement for each bit in address
          Transition is HL or LH.
          Should be called before the write command itself
          """
        self.saved_nodes.update(address_labels)

        self.setup_power_measurement("WRITE", transition, address_int)
        for label in address_labels:
            self.setup_delay_measurement(transition, label,
                                   delay_name="W_DELAY_{}_a{}_{}".format(transition, address_int, label),
                                   slew_name="W_SLEW_{}_a{}_{}".format(transition, address_int, label))

