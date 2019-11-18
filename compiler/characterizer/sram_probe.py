from subprocess import check_output, CalledProcessError

import numpy as np

import debug
from globals import OPTS
import tech
from base import utils


class SramProbe(object):
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
        self.decoder_probes = {}
        self.probe_labels = set()

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
                pin = utils.get_libcell_pins([pin_name], "cell_6t", tech.GDS["unit"],
                                             tech.layer["boundary"]).get(pin_name)[0]
        else:
            pin = None

        pin_labels = [""] * self.sram.word_size
        for i in range(self.sram.word_size):
            col = i * self.sram.words_per_row + self.address_to_int(col_index)
            if OPTS.use_pex:
                ll, ur = self.get_bitcell_pin(pin, bank_inst, row, col)
                pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
                pin_label = "{}_b{}r{}c{}".format(pin_name, bank_index, row, col)
                self.sram.add_label(pin_label, pin.layer, pin_loc, zoom=0.025)
                pin_labels[i] = pin_label
            else:
                pin_labels[i] = self.get_bitcell_label(bank_index, row, col, pin_name)
        pin_labels.reverse()
        self.probe_labels.update(pin_labels)

        if pin_name not in self.bitcell_probes:
            self.bitcell_probes[pin_name] = {}
        self.bitcell_probes[pin_name][address_int] = pin_labels

    def get_bitcell_pin(self, pin, bank_inst, row, col):
        return utils.get_pin_rect(pin, [bank_inst, bank_inst.mod.bitcell_array_inst,
                                              bank_inst.mod.bitcell_array_inst.mod.cell_inst[row, col]])

    def get_bitcell_label(self, bank_index, row, col, pin_name):
        return "Xsram.Xbank{}.Xbitcell_array.Xbit_r{}_c{}.{}".format(bank_index, row, col, pin_name)

    def get_bitcell_probes(self, address, pin_name="Q", pex_file=None):
        """Retrieve simulation probe name based on extracted file"""
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

    def get_bitcell_storage_nodes(self):
        nodes_map = {}
        pattern = self.get_storage_node_pattern()
        for address in range(self.sram.num_words):
            bank_index, bank_inst, row, col_index = self.decode_address(address)
            address_nodes = [""]*self.sram.word_size
            nodes_map[address] = address_nodes
            for i in range(self.sram.word_size):
                col = i * self.sram.words_per_row + self.address_to_int(col_index)
                address_nodes[i] = pattern.format(bank=bank_index, row=row, col=col)
        return nodes_map

    def get_storage_node_pattern(self):
        general_pattern = list(self.bitcell_probes.values())[0][0]  # type: str

        def sub_specific(pattern, prefix, key):
            pattern = re.sub(prefix + "\[[0-9]+\]", prefix + "[{" + key + "}]", pattern)
            delims = ["_", "\."]
            replacements = ["_", "."]
            for i in range(2):
                delim = delims[i]
                replacement = replacements[i]
                pattern = re.sub(delim + prefix + "[0-9]+",
                                 replacement + prefix + "{" + key + "}",
                                 pattern)
            return pattern

        general_pattern = sub_specific(general_pattern, "Xbank", "bank")
        general_pattern = sub_specific(general_pattern, "r", "row")
        general_pattern = sub_specific(general_pattern, "c", "col")
        return general_pattern

    def get_decoder_probes(self, address):
        if OPTS.use_pex:
            return self.extract_from_pex(self.decoder_probes[address])
        else:
            return self.decoder_probes[address]

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
                pin, ll, ur = self.get_bitline_pin(pin_name, bank_inst, col)
                pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
                pin_label = "{}_b{}c{}".format(pin_name, bank_index, col)
                self.sram.add_label(pin_label, pin.layer, pin_loc, zoom=0.05)
                pin_labels[i] = pin_label
            else:
                pin_labels[i] = self.get_bitline_label(bank_index, pin_name, col)
        pin_labels.reverse()
        self.probe_labels.update(pin_labels)
        self.bitline_probes[label_key] = pin_labels

    def get_bitline_label(self, bank_index, pin_name, col):
        return "Xsram.Xbank{}.Xbitcell_array.{}[{}]".format(bank_index, pin_name, col)

    def get_bitline_pin(self, pin_name, bank_inst, col):
        pin = bank_inst.mod.bitcell_array_inst.get_pin("{}[{}]".format(pin_name, col))
        ll, ur = utils.get_pin_rect(pin, [bank_inst])
        return pin, ll, ur


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
        bank_index, bank_inst, row, col_index = self.decode_address(address)

        label_key = "wl_b{}_r{}".format(bank_index, row)

        if label_key in self.wordline_probes:
            return

        if OPTS.use_pex:
            pin, ll, ur = self.get_wordline_pin(bank_inst, row, col_index)
            pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
            self.sram.add_label(label_key, pin.layer, pin_loc)
            self.wordline_probes[label_key] = label_key
        else:
            self.wordline_probes[label_key] = self.get_wordline_label(bank_index, row, col_index)
        self.probe_labels.add(self.wordline_probes[label_key])

    def probe_decoder_outputs(self, address_int):
        """add labels to wordlines
                labels should be unique by bank and row
                """

        address = self.address_to_vector(address_int)
        bank_index, bank_inst, row, col_index = self.decode_address(address)

        if OPTS.use_pex:
            decoder_label = "dec_b{}_r{}".format(bank_index, row)
            decoder_pin = bank_inst.mod.decoder.get_pin("decode[{}]".format(row))
            self.add_pin_label(decoder_pin, [bank_inst, bank_inst.mod.row_decoder_inst], decoder_label)
        else:
            decoder_label = "Xsram.Xbank{}.dec_out[{}]".format(bank_index, row)
        self.decoder_probes[address_int] = decoder_label
        self.probe_labels.add(decoder_label)

    def get_wordline_label(self, bank_index, row, col_index):
        return "Xsram.Xbank{}.Xbitcell_array.wl[{}]".format(bank_index, row)

    def get_wordline_pin(self, bank_inst, row, col_index):
        pin = bank_inst.mod.bitcell_array_inst.get_pin("wl[{}]".format(row))
        ll, ur = utils.get_pin_rect(pin, [bank_inst])
        return pin, ll, ur

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
            self.probe_labels.add(pin_label)
            pin_labels.append(pin_label)
        self.sense_amp_probes[label_key] = pin_labels

    def get_sense_amp_probes(self, bank_index, pin_name, pex_file=None):
        label_key = "sa_b{}_{}".format(bank_index, pin_name)
        if label_key not in self.sense_amp_probes:
            debug.error("sense amp probes must be added first")
        if OPTS.use_pex:
            return list(map(lambda x: self.extract_from_pex(x, pex_file), self.sense_amp_probes[label_key]))
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
            pin_label = "Xsram.Xbank{}.Xwordline_driver.en".format(bank_index)
        self.probe_labels.add(pin_label)
        self.word_driver_clk_probes[label_key] = pin_label

    def get_word_driver_clk_probes(self, bank_index, pex_file=None):
        label_key = "dec_b{}_clk".format(bank_index)
        probe_name = self.word_driver_clk_probes[label_key]
        if OPTS.use_pex:
            return [self.extract_from_pex(probe_name, pex_file)]
        else:
            return [probe_name]

    def add_misc_bank_probes(self, bank_inst, bank_index):
        if OPTS.use_pex:
            self.probe_pin(bank_inst.mod.sense_amp_array_inst.get_pin("en"), "sense_amp_en_b{}".format(bank_index),
                            [bank_inst])
            self.probe_pin(bank_inst.mod.precharge_array_inst.get_pin("en"), "precharge_en_b{}".format(bank_index),
                            [bank_inst])
            self.probe_pin(bank_inst.mod.write_driver_array_inst.get_pin("en"), "write_en_b{}".format(bank_index),
                            [bank_inst])
            self.probe_pin(bank_inst.mod.tri_gate_array_inst.get_pin("en"), "tri_en_b{}".format(bank_index),
                            [bank_inst])
            self.probe_pin(bank_inst.mod.tri_gate_array_inst.get_pin("en_bar"), "tri_en_bar_b{}".format(bank_index),
                            [bank_inst])
            if self.sram.words_per_row > 1:
                self.probe_pin(bank_inst.mod.col_mux_array_inst.get_pin("sel[0]"), "mux_sel_0_b{}".format(bank_index),
                                [bank_inst])
            self.probe_pin(bank_inst.mod.write_driver_array_inst.get_pin("data[0]"), "write_d0_b{}".format(bank_index),
                            [bank_inst])
            # self.probe_pin(bank_inst.mod.wordline_driver_inst.get_pin("in[0]"), "wl_drv_in0_b{}".format(bank_index),
            #                 [bank_inst])
            self.probe_pin(bank_inst.mod.wordline_driver_inst.mod.module_insts[0].get_pin("Z"),
                            "wl_drv_en_bar_b{}".format(bank_index),
                            [bank_inst, bank_inst.mod.wordline_driver_inst])
            self.probe_pin(bank_inst.mod.wordline_driver_inst.mod.module_insts[1].get_pin("Z"),
                            "wl_drv_net0_b{}".format(bank_index),
                            [bank_inst, bank_inst.mod.wordline_driver_inst])
            for i in range(self.sram.bank.row_addr_size):
                self.probe_pin(bank_inst.mod.row_decoder_inst.get_pin("A[{}]".format(i)), "decoder_in_{}".format(i),
                               [bank_inst])

    def add_misc_probes(self, bank_inst):
        self.probe_pin(bank_inst.get_pin("clk_buf"), "clk_buf", [])
        self.probe_pin(bank_inst.get_pin("tri_en"), "ctrl_tri_en", [])
        self.probe_pin(bank_inst.get_pin("w_en"), "ctrl_w_en", [])
        self.probe_pin(bank_inst.get_pin("s_en"), "ctrl_s_en", [])

    def probe_pin(self, pin, label, module_list):
        ll, ur = utils.get_pin_rect(pin, module_list)
        self.sram.add_label(label, pin.layer, ll)
        self.probe_labels.add(label)

    def extract_from_pex(self, label, pex_file=None):
        if pex_file is None:
            pex_file = self.pex_file

        match = None
        try:
            label_sub = label.replace("Xsram.", "").replace(".", "_")\
                .replace("[", "\[").replace("]", "\]")
            pattern = "\sN_{}_[MX]\S+_[gsd]".format(label_sub)
            match = check_output(["grep", "-m1", "-o", "-E", pattern, pex_file])

        except CalledProcessError as ex:
            if ex.returncode == 1:  # mismatch
                try:
                    # lvs box pins have exact match without mangling so search for exact match without regex
                    match = check_output(["grep", "-m1", "-Fo", label, pex_file])
                except CalledProcessError as ex:
                    if ex.returncode == 1:
                        debug.error("Match not found in pex file for label {} {}".format(label, pattern))
                        raise ex
                    else:
                        raise ex
            else:
                raise ex

        return 'Xsram.' + match.decode().strip()

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
        col_address = address[:no_col_bits] or [0]
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
        self.sram.objs = list(filter(lambda x: not x.name == "label", self.sram.objs))

    def add_pin_label(self, pin, module_insts, label_key):
        ll, ur = utils.get_pin_rect(pin, module_insts)
        pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
        # self.sram.add_rect(pin.layer, offset=ll, width=pin.width(), height=pin.height())
        self.sram.add_label(label_key, pin.layer, pin_loc)
