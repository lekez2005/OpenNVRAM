from subprocess import CalledProcessError

import debug
from base import utils
from characterizer.sram_probe import SramProbe
from globals import OPTS


class BlProbe(SramProbe):
    """
    Adds probe labels to the sram such that the label names are partially retained post extraction
    The actual post extraction label is obtained using regex
    """

    def __init__(self, sram, pex_file=None):
        super().__init__(sram, pex_file)

        self.state_probes = {}
        self.sense_amp_probes = {}
        self.and_probes = {}
        self.nor_probes = {}
        self.decoder_probes = {}
        self.dout_probes = {}
        self.current_probes = set()

    def probe_bitlines(self, bank):
        for col in range(self.sram.num_cols):
            for pin_name in ["bl", "br"]:
                pin_label = "Xsram.Xbank{}.{}[{}]".format(bank, pin_name, col)
                self.probe_labels.add(pin_label)
                if pin_name == "bl":
                    self.bitline_probes[col] = pin_label

    def probe_write_drivers(self):
        """Probe write driver internal bl_bar, br_bar and write currents"""
        if OPTS.use_pex:
            current_template = "Xsram.mXbank0_Xwrite_driver_array_Xdriver_{}_MM{}:d"
        else:
            current_template = "Xsram.Xbank.Xwrite_driver_array.Xdriver_{}.MM{}:d"

        # current transistors bl_nmos, bl_pmos, br_nmos, br_pmos
        current_transistors = [3, 4, 11, 12]

        for col in range(self.sram.num_cols):
            for pin_name in ["bl_bar", "br_bar"]:
                pin_label = "Xsram.Xbank{}.Xwrite_driver_array.Xdriver_{}.{}".\
                    format(0, col, pin_name)
                self.probe_labels.add(pin_label)

            for tx_num in current_transistors:
                self.current_probes.add(current_template.format(col, tx_num))

    def probe_misc_bank(self, bank):

        nets = ["clk_buf", "wordline_en", "precharge_en", "write_en", "sense_en", "sense_en_bar"]

        for net in nets:
            self.probe_labels.add("Xsram.Xbank{}.{}".format(bank, net))

        labels = ["clk_bank_sel_bar_int", "clk_bank_sel", "clk_bank_sel_bar"]

        for i in range(len(labels)):
            self.probe_labels.add("Xsram.Xbank{}.Xcontrol_buffers.{}".format(bank, labels[i]))

        for i in range(len(self.sram.bank.control_buffers.clk_buf.buffer_stages)-2):
            self.probe_labels.add("Xsram.Xbank{}.Xcontrol_buffers.Xclk_buf.out_{}".format(bank, i+1))
        self.probe_labels.add("Xsram.Xbank{}.Xcontrol_buffers.clk_bar".format(bank, i+1))

    def probe_address(self, address, pin_name="Q"):

        address = self.address_to_vector(address)
        address_int = self.address_to_int(address)

        bank_index, bank_inst, row, col_index = self.decode_address(address)

        if OPTS.baseline:
            decoder_label = "Xsram.Xbank{}.dec_out_0[{}]".format(bank_index, row)
        else:
            decoder_label = "Xsram.Xbank{}.wl_in[{}]".format(bank_index, row)
        self.decoder_probes[address_int] = decoder_label
        self.probe_labels.add(decoder_label)

        wl_label = "Xsram.Xbank{}.wl[{}]".format(bank_index, row)
        self.wordline_probes[address_int] = wl_label
        self.probe_labels.add(wl_label)

        pin_labels = [""] * self.sram.word_size
        for col in range(self.sram.num_cols):
            pin_labels[col] = "Xsram.Xbank{}.Xbitcell_array.Xbit_r{}_c{}.{}".format(bank_index, row, col, pin_name)

        self.probe_labels.update(pin_labels)
        self.state_probes[address_int] = pin_labels

    def extract_probes(self):
        """Extract probes from extracted pex file"""
        if OPTS.use_pex:
            self.saved_nodes = set()
            for label in self.probe_labels:
                try:
                    self.saved_nodes.add(self.extract_from_pex(label))
                except CalledProcessError:
                    debug.warning("Probe {} not found in extracted netlist".format(label))
            try:
                for col, col_label in self.bitline_probes.items():
                    self.bitline_probes[col] = self.extract_from_pex(col_label)
                for address, address_label in self.decoder_probes.items():
                    self.decoder_probes[address] = self.extract_from_pex(address_label)
                for address, address_labels in self.state_probes.items():
                    self.state_probes[address] = [self.extract_from_pex(address_label)
                                                  for address_label in address_labels]
            except CalledProcessError:  # ignore missing probe errors
                pass
        else:
            self.saved_nodes = set(self.probe_labels)
