# pip install libpsf (patched version available at https://github.com/lekez2005/libpsf
import libpsf
import numpy as np


class SimulationData(object):

    data = time = vdd = None
    is_open = False

    def __init__(self, simulation_file, vdd_name="vdd"):
        self.simulation_file = simulation_file
        self.vdd_name = vdd_name

        self.initialize()

    def initialize(self):
        self.data = libpsf.PSFDataSet(self.simulation_file)
        self.time = self.data.get_sweep_values()
        self.vdd = self.data.get_signal(self.vdd_name)[0]
        self.is_open = True

    def close(self):
        self.data.close()
        self.is_open = False

    def find_nearest(self, time_t):
        idx = (np.abs(self.time - time_t)).argmin()
        return idx

    def slice_array(self, array_, from_t=0.0, to_t=None):
        if to_t is None:
            to_t = self.time[-1]
        from_index = self.find_nearest(from_t)
        to_index = self.find_nearest(to_t)

        if from_index == to_index:
            return np.asarray(array_[from_index])
        elif to_index == array_.size - 1:
            return array_[from_index:]
        else:
            return array_[from_index:to_index+1]

    def get_signal(self, signal_name, from_t=0.0, to_t=None):

        if not self.is_open:
            self.initialize()
        signal = self.data.get_signal(signal_name)
        return self.slice_array(signal, from_t, to_t)

    def get_binary(self, signal_name, time_t):
        signal = self.get_signal(signal_name, from_t=time_t, to_t=time_t)
        return 1 * (signal.flatten() > 0.5*self.vdd)

    def get_bus(self, bus_pattern, bus_size, from_t=0.0, to_t=None):
        # type: (str, int, float, float) -> np.ndarray
        sig_zero = self.get_signal(bus_pattern.format(0), from_t, to_t)
        result = np.zeros([sig_zero.size, bus_size])
        result[:, 0] = sig_zero
        for i in range(1, bus_size):
            result[:, i] = self.get_signal(bus_pattern.format(i), from_t, to_t)
        return result


    def get_bus_binary(self, bus_pattern, bus_size, time_t):
        bus_data = self.get_bus(bus_pattern, bus_size, time_t, time_t)
        bus_data = bus_data.flatten()
        return 1*np.flipud(bus_data > 0.5*self.vdd)
