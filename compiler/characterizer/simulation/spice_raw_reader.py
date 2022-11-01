#!/usr/bin/env python3
"""
Read spice raw format
TODO: complex values
TODO: Doesn't work for spectre's nutbin/nutascii
"""
import re
import struct
import sys
import numpy as np

from psf_reader import PsfReader

HEADER_REGEX = re.compile(r"^(.*):\s+(.*)")
BINARY = "binary"
ASCII = "ascii"


class SpiceData:

    def __init__(self, simulation_file):
        self.signals = {}
        self.header = {}
        self.simulation_file = simulation_file
        self.parse_header()
        self.load_data()

    def parse_header(self):
        in_signals = False
        with open(self.simulation_file, "rb") as f:
            while True:
                line = f.readline()
                if not line:
                    break
                line = line.decode(encoding="ascii").strip()
                if line.lower() == "values:":
                    self.data_offset = f.tell()
                    self.format = ASCII
                    break
                elif line.lower() == "binary:":
                    self.data_offset = f.tell()
                    self.format = BINARY
                    break
                elif line.lower().startswith("variables:"):
                    in_signals = True
                elif in_signals:
                    index, signal_name, signal_type = line.split()[:3]
                    self.signals[signal_name.lower()] = int(index)
                elif not in_signals:
                    # headers
                    match = HEADER_REGEX.match(line)
                    if match:
                        self.header[match.groups()[0]] = match.groups()[1]
        self.num_points = int(self.header["No. Points"])
        self.num_signals = int(self.header["No. Variables"])

    def load_data(self):
        if self.format == BINARY:
            with open(self.simulation_file, "rb") as f:
                f.seek(self.data_offset)
                self.data_binary = f.read()
        else:
            with open(self.simulation_file, "r") as f:
                f.seek(self.data_offset)
                self.data_lines = [line.strip() for line in f.readlines() if line.strip()]

    def get_signal(self, signal_name):
        values = []
        index = self.signals[signal_name]
        for i in range(self.num_points):
            value_index = i * self.num_signals + index
            if self.format == ASCII:
                value = float(self.data_lines[value_index].split()[-1])
            else:
                byte_offset = 8 * value_index
                value = struct.unpack("<d", self.data_binary[byte_offset:byte_offset + 8])[0]
            values.append(value)
        return np.array(values)

    def get_sweep_values(self):
        return self.get_signal("time")


class SpiceRawReader(PsfReader):

    def create_data(self):
        self.data = SpiceData(self.simulation_file)

    def get_signal_names(self):
        return list(self.data.signals.keys())

    def close(self):
        pass


if __name__ == "__main__":
    file_name_ = sys.argv[1]
    reader = SpiceRawReader(file_name_)
    time = reader.get_signal("time")
    print(time)
