from subprocess import check_output

import numpy as np

import debug
from globals import OPTS
import tech
import utils


class SramProbe:
    """
    Define methods to probe internal SRAM nets given address info
    Mostly geared towards extracted simulations since node names aren't preserved during extraction
    """

    def __init__(self, sram, pex_file=None):
        self.sram = sram
        if pex_file is None:
            self.pex_file = OPTS.pex_spice
        else:
            self.pex_file = pex_file

        self.q_pin = utils.get_libcell_pins(["Q"], "cell_6t", tech.GDS["unit"], tech.layer["boundary"]).get("Q")[0]
        self.qbar_pin = \
        utils.get_libcell_pins(["QBAR"], "cell_6t", tech.GDS["unit"], tech.layer["boundary"]).get("QBAR")[0]

        self.bitcell_probes = {}
        self.bitline_probes = {}
        self.wordline_probes = {}
        self.sense_amp_probes = {}
        self.word_driver_clk_probes = {}

    def probe_bit_cells(self, address, pin_name="Q"):
        """Probe Q, QBAR of bitcell"""
        address = self.address_to_vector(address)
        address_int = self.address_to_int(address)

        if pin_name not in self.bitcell_probes:
            self.bitcell_probes[pin_name] = {}

        if address_int in self.bitcell_probes[pin_name]:
            return

        bank_index, bank_inst, row, col_index = self.decode_address(address)

        if OPTS.use_pex:
            if pin_name == "Q":
                pin = self.q_pin
            elif pin_name == "QBAR":
                pin = self.qbar_pin
            else:
                pin = \
                utils.get_libcell_pins([pin_name], "cell_6t", tech.GDS["unit"], tech.layer["boundary"]).get(pin_name)[0]
        else:
            pin = None

        pin_labels = [""] * self.sram.word_size
        for i in range(self.sram.word_size):
            col = i * self.sram.words_per_row + self.address_to_int(col_index)
            if OPTS.use_pex:
                ll, ur = utils.get_pin_rect(pin, [bank_inst, bank_inst.mod.bitcell_array_inst,
                                                  bank_inst.mod.bitcell_array_inst.mod.cell_inst[row, col]])
                pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
                pin_label = "{}_b{}r{}c{}".format(pin_name, bank_index, row, col)
                self.sram.add_label(pin_label, pin.layer, pin_loc, zoom=0.025)
                pin_labels[i] = pin_label
            else:
                pin_labels[i] = "Xsram.Xbank{}.Xbitcell_array.Xbit_r{}_c{}.{}".format(bank_index, row, col, pin_name)
        pin_labels.reverse()

        if pin_name not in self.bitcell_probes:
            self.bitcell_probes[pin_name] = {}
        self.bitcell_probes[pin_name][address_int] = pin_labels

    def get_bitcell_probes(self, address, pin_name="Q", pex_file=None):
        """Retrieve somulation probe name based on extracted file"""
        address = self.address_to_vector(address)
        address_int = self.address_to_int(address)

        if pin_name not in self.bitcell_probes or address_int not in self.bitcell_probes[pin_name]:
            debug.error("invalid pin name/address")
        pin_labels = self.bitcell_probes[pin_name][address_int]

        if not OPTS.use_pex:
            return pin_labels[:]
        else:
            pin_labels_pex = []
            for label in pin_labels:
                pin_labels_pex.append(self.extract_from_pex(label, pex_file))
            return pin_labels_pex

    def probe_bit_lines(self, address, pin_name="bl"):
        """add labels to bitlines
        labels should be unique by bank and col_index
        """

        address = self.address_to_vector(address)
        bank_index, bank_inst, _, col_index = self.decode_address(address)

        label_key = "{}_b{}c{}".format(pin_name, bank_index, col_index)

        if label_key in self.bitline_probes:
            return

        pin_labels = [""] * self.sram.word_size
        for i in range(self.sram.word_size):
            col = i * self.sram.words_per_row + self.address_to_int(col_index)
            if OPTS.use_pex:
                pin = bank_inst.mod.bitcell_array_inst.get_pin("{}[{}]".format(pin_name, col))
                ll, ur = utils.get_pin_rect(pin, [bank_inst])
                pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
                pin_label = "{}_b{}c{}".format(pin_name, bank_index, col)
                self.sram.add_label(pin_label, pin.layer, pin_loc, zoom=0.05)
                pin_labels[i] = pin_label
            else:
                pin_labels[i] = "Xsram.Xbank{}.Xbitcell_array.{}[{}]".format(bank_index, pin_name, col)
        pin_labels.reverse()
        self.bitline_probes[label_key] = pin_labels

    def get_bitline_probes(self, address, pin_name="bl", pex_file=None):
        """Retrieve simulation probe names based on extracted file"""
        address = self.address_to_vector(address)
        bank_index, bank_inst, _, col_index = self.decode_address(address)

        label_key = "{}_b{}c{}".format(pin_name, bank_index, col_index)
        if label_key not in self.bitline_probes:
            debug.error("address should be added first")

        pin_labels = self.bitline_probes[label_key]
        if not OPTS.use_pex:
            return pin_labels[:]
        else:
            extracted_labels = []
            for label in pin_labels:
                extracted_labels.append(self.extract_from_pex(label, pex_file))
            return extracted_labels

    def probe_wordlines(self, address):
        """add labels to wordlines
                labels should be unique by bank and row
                """

        address = self.address_to_vector(address)
        bank_index, bank_inst, row, _ = self.decode_address(address)

        label_key = "wl_b{}_r{}".format(bank_index, row)

        if label_key in self.wordline_probes:
            return

        if OPTS.use_pex:
            pin = bank_inst.mod.bitcell_array_inst.get_pin("wl[{}]".format(row))
            ll, ur = utils.get_pin_rect(pin, [bank_inst])
            pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
            self.sram.add_label(label_key, pin.layer, pin_loc)
            self.wordline_probes[label_key] = label_key
        else:
            self.wordline_probes[label_key] = "Xsram.Xbank{}.Xbitcell_array.wl[{}]".format(bank_index, row)

    def get_wordline_probes(self, address, pex_file=None):
        address = self.address_to_vector(address)
        bank_index, bank_inst, row, _ = self.decode_address(address)

        label_key = "wl_b{}_r{}".format(bank_index, row)
        if label_key not in self.wordline_probes:
            debug.error("address should be added first")

        if OPTS.use_pex:
            return [self.extract_from_pex(label_key, pex_file)]
        else:
            return [self.wordline_probes[label_key]]

    def probe_sense_amps(self, bank_index, bank_inst, pin_name):
        """Add probes to bl, br or data pins of sense_amp_array """
        label_key = "sa_b{}_{}".format(bank_index, pin_name)
        if label_key in self.sense_amp_probes:
            return
        pin_labels = []
        for i in range(self.sram.word_size):
            if pin_name == "data":
                col = i
            else:
                col = i * self.sram.words_per_row
            if OPTS.use_pex:
                pin = bank_inst.mod.sense_amp_array_inst.get_pin("{}[{}]".format(pin_name, col))
                ll, ur = utils.get_pin_rect(pin, [bank_inst])
                pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
                pin_label = "sa_{}_b{}c_{}".format(pin_name, bank_index, col)
                self.sram.add_label(pin_label, pin.layer, pin_loc)
                pin_labels.append(pin_label)
                self.sense_amp_probes[label_key] = label_key
            else:
                pin_label = "Xsram.Xbank{}.Xsense_amp_array.{}[{}]".format(bank_index, pin_name, col)
            pin_labels.append(pin_label)
        self.sense_amp_probes[label_key] = pin_labels

    def get_sense_amp_probes(self, bank_index, pin_name, pex_file=None):
        label_key = "sa_b{}_{}".format(bank_index, pin_name)
        if label_key not in self.sense_amp_probes:
            debug.error("sense amp probes must be added first")
        if OPTS.use_pex:
            return map(lambda x: self.extract_from_pex(x, pex_file), self.sense_amp_probes[label_key])
        else:
            return self.sense_amp_probes[label_key]

    def probe_word_driver_clk(self, bank_index, bank_inst):
        label_key = "dec_b{}_clk".format(bank_index)
        if label_key in self.word_driver_clk_probes:
            return
        if OPTS.use_pex:
            pin = bank_inst.mod.wordline_driver_inst.get_pin("en")
            ll, ur = utils.get_pin_rect(pin, [bank_inst])
            pin_label = label_key
            self.sram.add_label(pin_label, pin.layer, ll)
        else:
            pin_label = "Xsram.Xbank{}.Xwordline_driver.clk_buf".format(bank_index)
        self.word_driver_clk_probes[label_key] = pin_label

    def get_word_driver_clk_probes(self, bank_index, pex_file=None):
        label_key = "dec_b{}_clk".format(bank_index)
        probe_name = self.word_driver_clk_probes[label_key]
        if OPTS.use_pex:
            return [self.extract_from_pex(probe_name, pex_file)]
        else:
            return [probe_name]

    def probe_pin(self, pin, label, module_list):
        ll, ur = utils.get_pin_rect(pin, module_list)
        self.sram.add_label(label, pin.layer, ll)

    def extract_from_pex(self, label, pex_file=None):
        if pex_file is None:
            pex_file = self.pex_file
        pattern = "\sN_{}\S+_[gsd]".format(label)
        match = check_output(["grep", "-m1", "-o", "-E", pattern, pex_file])
        if match and match.strip():
            return 'Xsram.' + match.strip()
        else:
            debug.error("Match not found in pex file for label {}".format(label))

    def decode_address(self, address):
        if self.sram.num_banks == 4:
            bank_index = 2 ** address[0] + address[1]
            bank_inst = self.sram.bank_inst[bank_index]
            address = address[2:]
        elif self.sram.num_banks == 2:
            bank_index = address[0]
            bank_inst = self.sram.bank_inst[bank_index]
            address = address[1:]
        else:
            bank_index = 0
            bank_inst = self.sram.bank_inst

        words_per_row = self.sram.words_per_row
        no_col_bits = int(np.log2(words_per_row))
        col_address = address[:no_col_bits]
        row_address = address[no_col_bits:]
        row = self.address_to_int(row_address)
        col_index = self.address_to_int(col_address)

        return bank_index, bank_inst, row, col_index

    def address_to_vector(self, address):
        """Convert address integer to binary list MSB first"""
        if type(address) == int:
            return list(map(int, np.binary_repr(address, width=self.sram.addr_size)))
        elif type(address) == list and len(address) == self.sram.addr_size:
            return address
        else:
            debug.error("Invalid address: {}".format(address))

    def address_to_int(self, address):
        """address is vector of integers MSB first"""
        if type(address) == int:
            return address
        elif type(address) == list:
            return int("".join(str(a) for a in address), base=2)
        else:
            debug.error("Invalid data: {}".format(address))

    def clear_labels(self):
        self.sram.objs = filter(lambda x: not x.name == "label", self.sram.objs)
