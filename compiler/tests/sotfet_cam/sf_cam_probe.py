from subprocess import CalledProcessError

import debug
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

    def probe_search_lines(self, bank):
        for i in range(self.sram.num_cols):
            for net in ["sl", "slb"]:
                self.probe_labels.add("Xsram.Xbank{}.{}[{}]".format(bank, net, i))

    def get_bitcell_label(self, bank_index, row, col, pin_name):
        if self.sotfet:
            return "Xsram.Xbank{}.Xbitcell_array.mz1_c{}_r{}".format(bank_index, col, row)
        else:
            return "Xsram.Xbank{}.Xbitcell_array.Xbit_r{}_c{}.{}".format(bank_index, row, col, pin_name)

    def get_bitline_label(self, bank, col, label, row):
        if OPTS.use_pex and not self.sotfet:  # select top right bitcell
            pin_label = "Xsram.Xbank{bank}_{pin_name}[{col}]_Xbank{bank}_Xbitcell_array" \
                        "_Xbit_r{row}_c{col}".format(bank=bank, col=col, pin_name=label, row=row)
        else:
            pin_label = "Xsram.Xbank{}.{}[{}]".format(bank, label, col)
        return pin_label

    def get_clk_probe(self, bank=0):
        if OPTS.use_pex:
            return "Xsram.Xbank{bank}_gated_clk_buf_Xbank{bank}_Xlogic_buffers".format(bank=bank)
        else:
            return "Xsram.Xbank{}.gated_clk_buf".format(bank)

    def probe_misc_bank(self, bank):

        nets = {
            "clk_buf": "Xmask_in_Xdff{col}",
            "wordline_en": "Xwordline_driver_Xdriver{row}",
            "matchline_chb": "Xml_precharge_array_Xprecharge_{row}",
            "write_bar": "Xbitline_logic_Xbitline_logic{col}",
            "search_cbar": "Xbitline_logic_Xbitline_logic{col}",
            "sense_amp_en": "Xsearch_sense_amps_Xamp[{row}]"
        }

        net_keys = ["clk_buf", "sense_amp_en", "wordline_en", "matchline_chb"]
        if self.sotfet:
            net_keys += ["write_bar", "search_cbar"]

        for key in net_keys:
            if OPTS.use_pex:
                prefix = "Xsram.Xbank{0}_{1}_Xbank{0}_".format(bank, "gated_" + key)

                self.probe_labels.add(prefix + "Xlogic_buffers")
                if OPTS.verbose_save:
                    if "col" in nets[key]:
                        for col in range(self.sram.num_cols):
                            suffix = ""
                            if key in ["write_bar", "search_cbar", "clk_buf"]:
                                if col % 2 == 1:
                                    continue
                                if self.sotfet:
                                    suffix = "_{}".format(col+1)
                            self.probe_labels.add(prefix + nets[key].format(col=col) + suffix)
                    elif "row" in nets[key]:
                        for row in range(self.sram.num_rows):
                            self.probe_labels.add(prefix + nets[key].format(row=row))

            else:
                self.probe_labels.add("Xsram.Xbank{}.{}".format(bank, "gated_" + key))

            # output of data_in flops
            if OPTS.verbose_save:
                for col in range(self.sram.num_cols):
                    if OPTS.use_pex:
                        self.probe_labels.add(
                            "Xsram.Xbank{bank}_data_in[{col}]_Xbank{bank}_Xdata_in".format(bank=bank, col=col))
                    else:
                        self.probe_labels.add("Xsram.Xbank{}.data_in[{}]".format(bank, col))

    def probe_address(self, address):

        address = self.address_to_vector(address)
        address_int = self.address_to_int(address)

        bank_index, bank_inst, row, col_index = self.decode_address(address)

        decoder_label = "Xsram.Xbank{}.dec_out[{}]".format(bank_index, row)
        self.decoder_probes[address_int] = decoder_label
        self.probe_labels.add(decoder_label)

        wl_label = self.get_wordline_label(bank_index, bank_index, self.sram.num_cols-1)
        self.wordline_probes[address_int] = wl_label

        pin_labels = [""] * self.sram.word_size
        for i in range(self.sram.num_cols):
            col = i * self.sram.words_per_row + self.address_to_int(col_index)
            pin_label = self.get_bitcell_label(bank_index, row, col, "Q")
            pin_labels[i] = pin_label

            # save internal VG node
            if OPTS.use_pex and self.sotfet:
                self.probe_labels.add("Xsram.Xbank0_Xbitcell_array_Xbit_r{}_c{}.XI8.VG".format(address_int, col))
                self.probe_labels.add("Xsram.Xbank0_Xbitcell_array_Xbit_r{}_c{}.XI8.I8.vg_nfet".format(address_int, col))
                self.probe_labels.add("Xsram.Xbank0_Xbitcell_array_Xbit_r{}_c{}.XI9.I8.vg_nfet".format(address_int, col))

        self.probe_labels.update(pin_labels)
        self.state_probes[address_int] = pin_labels
        self.bitcell_probes = self.state_probes

    def probe_matchline(self, address):
        address_int = address
        address = self.address_to_vector(address)
        bank_index, bank_inst, row, col_index = self.decode_address(address)
        # get rightmost matchline
        if OPTS.use_pex:
            label_key = "Xsram.Xbank{0}.ml[{1}]_Xbank{0}_Xsearch_sense_amps_Xamp[{1}]".format(bank_index, row)
            dout_key = "search_out[{1}]".format(bank_index, row)
        else:
            label_key = "Xsram.Xbank{}.ml[{}]".format(bank_index, row)
            dout_key = "search_out[{}]".format(bank_index, row)
        self.probe_labels.add(label_key)
        self.probe_labels.add(dout_key)
        self.matchline_probes[address_int] = label_key
        self.dout_probes[address_int] = dout_key

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
                self.clk_probe = self.extract_from_pex(self.clk_probe)
            except CalledProcessError as ex:
                pass
        else:
            self.saved_nodes = set(self.probe_labels)
        self.saved_nodes.update(self.matchline_probes.values())
        self.saved_nodes.update(self.dout_probes.values())
        self.saved_nodes.update(self.decoder_probes.values())
        for labels in self.state_probes.values():
            self.saved_nodes.update(labels)
        self.saved_nodes.add(self.clk_probe)

    def extract_from_pex(self, label, pex_file=None):
        if self.sotfet and "bitcell_array" in label:
            if "VG" in label or "vg_nfet" in label:
                return label.replace("Xsram_", "Xsram.")
            return label.replace(".", "_").replace("Xsram_", "Xsram.")
        if "search_out" in label:
            return label

        return super().extract_from_pex(label, pex_file)

    def get_matchline_probes(self):
        return [{"addr_int": key, "ml_label": value, "dout_label": self.dout_probes[key]}
                for (key, value) in self.matchline_probes.items()]
