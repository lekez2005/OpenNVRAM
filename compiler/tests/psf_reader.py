# pip install libpsf (patched version available at https://github.com/lekez2005/libpsf
import libpsf
import numpy as np


class PsfReader:

    data = time = vdd = None
    is_open = False

    RISING_EDGE = "rising"
    FALLING_EDGE = "falling"
    EITHER_EDGE = "either"

    FIRST_EDGE = "first"
    LAST_EDGE = "last"

    def __init__(self, simulation_file, vdd_name="vdd"):
        self.simulation_file = simulation_file
        self.vdd_name = vdd_name
        self.thresh = 0.5

        self.initialize()

    def initialize(self):
        self.data = libpsf.PSFDataSet(self.simulation_file)
        self.time = self.data.get_sweep_values()
        if self.vdd_name:
            self.vdd = self.data.get_signal(self.vdd_name)[0]
        self.is_open = True

        self.cache = {}

    def close(self):
        self.data.close()
        self.is_open = False

    def find_nearest(self, time_t):
        idx = (np.abs(self.time - time_t)).argmin()
        return idx

    def get_time_indices(self, from_t=0.0, to_t=None):
        if to_t is None:
            to_t = self.time[-1]
        from_index = self.find_nearest(from_t)
        to_index = self.find_nearest(to_t)
        return from_index, to_index

    def slice_array(self, array_, from_t=0.0, to_t=None):

        from_index, to_index = self.get_time_indices(from_t, to_t)

        if from_index == to_index:
            return np.asarray(array_[from_index])
        elif to_index == array_.size - 1:
            return array_[from_index:]
        else:
            return array_[from_index:to_index+1]

    def get_signal(self, signal_name, from_t=0.0, to_t=None):

        if not self.is_open:
            self.initialize()
        if signal_name in self.cache:
            signal = self.cache[signal_name]
        else:
            try:
                signal = self.data.get_signal(signal_name)
            except libpsf.NotFound:
                raise ValueError("Signal {} not found".format(signal_name))
            self.cache[signal_name] = signal
        return self.slice_array(signal, from_t, to_t)

    def get_signal_time(self, signal_name, from_t=0.0, to_t=None):
        return self.slice_array(self.time, from_t, to_t), self.get_signal(signal_name, from_t, to_t)

    def get_binary(self, signal_name, from_t, to_t=None, thresh=None):
        if to_t is None:
            to_t = from_t
        if thresh is None:
            thresh = self.thresh
        signal = self.get_signal(signal_name, from_t=from_t, to_t=to_t)
        return 1 * (signal.flatten() > thresh*self.vdd)

    def get_transition_time_thresh(self, signal_name, start_time, stop_time=None,
                                   edgetype=None, edge=None, thresh=None):
        if edge is None:
            edge = self.FIRST_EDGE
        if edgetype is None:
            edgetype = self.EITHER_EDGE
        if stop_time is None:
            stop_time = self.time[-1]
        if thresh is None:
            thresh = self.thresh
        signal_binary = self.get_binary(signal_name, start_time, to_t=stop_time, thresh=thresh)
        sig_prev = signal_binary[0]
        start_time_index = self.find_nearest(start_time)
        time = np.inf
        for i in range(len(signal_binary)):
            sig = signal_binary[i]
            if (sig != sig_prev) and (edgetype == self.EITHER_EDGE):
                time = self.time[i+start_time_index]
            elif (sig > sig_prev) and (edgetype == self.RISING_EDGE):
                time = self.time[i+start_time_index]
            elif (sig < sig_prev) and (edgetype == self.FALLING_EDGE):
                time = self.time[i+start_time_index]

            if edge == self.FIRST_EDGE and time != np.inf:
                return time
            sig_prev = sig
        return time

    def get_delay(self, signal_name1, signal_name2, t1=0, t2=None, stop_time=None, edgetype1=None,
                  edgetype2=None, edge1=None, edge2=None, thresh1=None, thresh2=None, num_bits=1, bit=0):

        if t2 is None:
            t2 = t1
        if stop_time is None:
            stop_time = self.time[-1]
        if edge1 is None:
            edge1 = self.FIRST_EDGE
        if edge2 is None:
            edge2 = self.FIRST_EDGE
        if edgetype1 is None:
            edgetype1 = self.EITHER_EDGE
        if edgetype2 is None:
            edgetype2 = edgetype1
        if thresh1 is None:
            thresh1 = self.thresh
        if thresh2 is None:
            thresh2 = self.thresh

        trans1 = self.get_transition_time_thresh(signal_name1, t1, stop_time, edgetype1, edge=edge1, thresh=thresh1)

        def internal_delay(name):
            trans2 = self.get_transition_time_thresh(name, t2, stop_time,
                                                     edgetype2, edge=edge2, thresh=thresh2)
            if trans1 == np.inf or trans2 == np.inf:
                return -np.inf  # -inf to make max calculations easier
            else:
                return trans2 - trans1

        if num_bits == 1:
            return internal_delay(signal_name2.format(bit))
        else:
            return list(reversed([internal_delay(signal_name2.format(i)) for i in range(num_bits)]))

    def get_signal_names(self):
        return self.data.get_signal_names()

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

