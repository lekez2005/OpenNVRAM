from subprocess import CalledProcessError

import debug
from base import utils
from characterizer.sram_probe import SramProbe
from globals import OPTS


class SfCamProbe(SramProbe):

    def __init__(self, sram, pex_file=None):
        super().__init__(sram, pex_file)

        if OPTS.bitcell == "cam_bitcell":
            self.bitcell = "cam_cell_6t"
            self.search_sense_amp = "search_sense_amp"
            self.sotfet = False
        else:
            self.bitcell = "sot_cam_cell"
            self.search_sense_amp = "sot_search_sense_amp"
            self.sotfet = True

        self.state_probes = {}
        self.matchline_probes = {}
        self.dout_probes = {}
        self.decoder_probes = {}

    def probe_bitlines(self, bank):
        bank_inst = self.sram.bank_inst
        num_rows = self.sram.num_rows
        for col in range(self.sram.num_cols):

            if OPTS.use_pex:
                for pin_name in ["BL", "BR"]:
                    pin = utils.get_libcell_pins([pin_name], self.bitcell).get(pin_name)[0]
                    pin_label = "{}_b{}_c{}".format(pin_name, bank, col)
                    self.add_pin_label(pin, [bank_inst, bank_inst.mod.bitcell_array_inst,
                                             bank_inst.mod.bitcell_array_inst.mod.cell_inst[num_rows-1, col]],
                                       pin_label)
                    self.probe_labels.add(pin_label)
            else:
                for pin_name in ["bl", "br"]:
                    self.probe_labels.add("Xsram.Xbank{}.{}[{}]".format(bank, pin_name, col))

    def probe_search_lines(self, bank):
        for i in range(self.sram.num_cols):
            for net in ["sl", "slb"]:
                self.probe_labels.add("Xsram.Xbank{}.{}[{}]".format(bank, net, i))

    def probe_misc_bank(self, bank):
        bank_inst = self.sram.bank_inst

        if self.sotfet:
            nets = ["write_bar", "search_cbar", "clk_buf", "sense_amp_en", "wordline_en"]
        else:
            nets = ["clk_bar", "clk_buf", "sense_amp_en", "wordline_en"]

        if OPTS.use_pex:
            nets.append("ml_chb")
            for net in nets:
                pin = bank_inst.mod.logic_buffers.get_pin(net)
                pin_label = "{}_b{}".format(net, bank)
                self.add_pin_label(pin, [bank_inst, bank_inst.mod.logic_buffers_inst], pin_label)
                self.probe_labels.add(pin_label)
            else:
                nets.append("matchline_chb")
                for net in nets:
                    self.probe_labels.add("Xsram.Xbank{}.{}".format(bank, "gated_" + net))

    def probe_address(self, address, pin_name=None):
        if self.sotfet:
            pin_name = "mz1"
        else:
            pin_name = "Q" if pin_name is None else pin_name
        pin = utils.get_libcell_pins([pin_name], self.bitcell).get(pin_name)[0]

        address = self.address_to_vector(address)
        address_int = self.address_to_int(address)

        bank_index, bank_inst, row, col_index = self.decode_address(address)

        if OPTS.use_pex:
            decoder_label = "dec_b{}_r{}".format(bank_index, row)
            decoder_pin = bank_inst.mod.decoder.get_pin("decode[{}]".format(row))
            self.add_pin_label(decoder_pin, [bank_inst, bank_inst.mod.row_decoder_inst], decoder_label)
        else:
            decoder_label = "Xsram.Xbank{}.dec_out[{}]".format(bank_index, row)
        self.decoder_probes[address_int] = decoder_label
        self.probe_labels.add(decoder_label)

        if OPTS.use_pex:
            wl_pin = utils.get_libcell_pins(["WL"], self.bitcell).get("WL")[0]
            wl_label = "wl_b{}_r{}".format(bank_index, row)
            self.add_pin_label(wl_pin, [bank_inst, bank_inst.mod.bitcell_array_inst,
                                     bank_inst.mod.bitcell_array_inst.mod.cell_inst[row, self.sram.num_cols - 1]],
                               wl_label)
            self.probe_labels.add(wl_label)
        else:
            wl_label = "Xsram.Xbank{}.wl[{}]".format(bank_index, row)
            self.wordline_probes[address_int] = wl_label
            self.probe_labels.add(wl_label)

            self.probe_labels.add("Xsram.Xbank{}.search_out[{}]".format(bank_index, row))

        pin_labels = [""] * self.sram.word_size
        for i in range(self.sram.num_cols):
            col = i * self.sram.words_per_row + self.address_to_int(col_index)
            if OPTS.use_pex:
                pin_label = "{}_b{}r{}c{}".format(pin_name, bank_index, row, col)
                self.add_pin_label(pin, [bank_inst, bank_inst.mod.bitcell_array_inst,
                                         bank_inst.mod.bitcell_array_inst.mod.cell_inst[row, col]], pin_label)
                pin_labels[i] = pin_label
            else:
                pin_labels[i] = "Xsram.Xbank{}.Xbitcell_array.Xbit_r{}_c{}.{}".format(bank_index, row, col, pin_name)

        self.probe_labels.update(pin_labels)
        self.state_probes[address_int] = pin_labels

    def probe_matchline(self, address):
        address_int = address
        address = self.address_to_vector(address)
        bank_index, bank_inst, row, col_index = self.decode_address(address)
        # get rightmost matchline
        if OPTS.use_pex:
            pin = utils.get_libcell_pins(["ML"], self.bitcell).get("ML")[0]
            label_key = "ml_r{}_b{}".format(row, bank_index)
            self.add_pin_label(pin, [bank_inst, bank_inst.mod.bitcell_array_inst,
                                     bank_inst.mod.bitcell_array_inst.mod.cell_inst[row, self.sram.num_cols-1]],
                               label_key)
            pin = utils.get_libcell_pins(["dout"], self.search_sense_amp).get("dout")[0]
            dout_key = "dout_r{}_b{}".format(row, bank_index)
            self.add_pin_label(pin, [bank_inst, bank_inst.mod.search_sense_inst,
                                     bank_inst.mod.search_sense_inst.mod.module_insts[row]],
                               dout_key)
        else:

            label_key = "Xsram.Xbank{}.ml[{}]".format(bank_index, row)
            dout_key = "Xsram.Xbank{}.search_out[{}]".format(bank_index, row)
        self.probe_labels.add(label_key)
        self.probe_labels.add(dout_key)
        self.matchline_probes[address_int] = label_key
        self.dout_probes[address_int] = dout_key

    def add_pin_label(self, pin, module_insts, label_key):
        ll, ur = utils.get_pin_rect(pin, module_insts)
        pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
        # self.sram.add_rect(pin.layer, offset=ll, width=pin.width(), height=pin.height())
        self.sram.add_label(label_key, pin.layer, pin_loc)

    def extract_probes(self):
        if OPTS.use_pex:
            self.saved_nodes = set()
            for label in self.probe_labels:
                try:
                    self.saved_nodes.add(self.extract_from_pex(label))
                except CalledProcessError:
                    debug.warning("Probe {} not found in extracted netlist".format(label))
            try:
                for address, address_label in self.matchline_probes.items():
                    self.matchline_probes[address] = self.extract_from_pex(address_label)
                for address, address_label in self.dout_probes.items():
                    self.dout_probes[address] = self.extract_from_pex(address_label)
                for address, address_label in self.decoder_probes.items():
                    self.decoder_probes[address] = self.extract_from_pex(address_label)
                for address, address_labels in self.state_probes.items():
                    self.state_probes[address] = [self.extract_from_pex(address_label)
                                                  for address_label in address_labels]
            except CalledProcessError as ex:
                pass
        else:
            self.saved_nodes = set(self.probe_labels)

    def get_matchline_probes(self):
        return [{"addr_int": key, "ml_label": value, "dout_label": self.dout_probes[key]}
                for (key, value) in self.matchline_probes.items()]
