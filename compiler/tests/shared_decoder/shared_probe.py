import debug
from characterizer.net_probes.sram_probe import SramProbe
from globals import OPTS


class SharedProbe(SramProbe):
    """
    Adds probe labels to the sram such that the label names are partially retained post extraction
    The actual post extraction label is obtained using regex
    """

    def __init__(self, sram, pex_file=None):
        super().__init__(sram, pex_file)
        debug.info(1, "Initialize sram probe")

        self.decoder_inputs_probes = {}
        self.dout_probes = self.voltage_probes["dout"] = {}
        self.mask_probes = self.voltage_probes["mask"] = {}

        self.external_probes.extend(["dout", "mask"])

        self.half_word = int(0.5 * self.word_size)

        for i in range(sram.word_size):
            self.dout_probes[i] = "D[{}]".format(i)
            self.mask_probes[i] = "mask[{}]".format(i)

        self.current_probes = set()

    def get_bitcell_storage_nodes(self):
        nodes_map = {}
        pattern = self.get_storage_node_pattern()
        for address in range(self.sram.num_words_per_bank):
            bank_index, bank_inst, row, col_index = self.decode_address(address)
            address_nodes = [""] * self.sram.word_size
            nodes_map[address] = address_nodes
            for i in range(self.word_size):
                col = i * self.sram.words_per_row + self.address_to_int(col_index)
                address_nodes[i] = pattern.format(bank=bank_index, row=row, col=col, name="Xbit")
                if self.two_bank_dependent:
                    address_nodes[i + self.word_size] = pattern.format(bank=1, row=row, col=col, name="Xbit")
        return nodes_map

    def get_w_label(self, bank_index, row, col):
        if OPTS.use_pex:
            wl_label = "Xsram.Xbank{bank}.wl[{row}]_Xbank{bank}" \
                       "_Xbitcell_array_Xbit_r{row}_c{col}".format(bank=bank_index, row=row, col=col)
        else:
            wl_label = "Xsram.Xbank{}.wl[{}]".format(bank_index, row)
        return wl_label

    def get_wordline_label(self, bank_index, row, col):
        return self.get_w_label(bank_index, row, col)

    @staticmethod
    def filter_internal_nets(child_mod, candidate_nets):
        netlist = child_mod.get_spice_parser().get_module(child_mod.name).contents
        netlist = "\n".join(netlist)

        results = []
        for net in candidate_nets:
            if " {} ".format(net) in netlist:
                results.append(net)
        return results

    def get_write_driver_internal_nets(self):
        child_mod = self.sram.bank.write_driver_array.child_mod
        pin_names = ["vdd"]
        candidate_nets = ["bl_bar", "br_bar", "data", "mask", "mask_bar", "bl_p", "br_p"]
        return pin_names + self.filter_internal_nets(child_mod, candidate_nets)

    def get_sense_amp_internal_nets(self):
        if OPTS.push:
            return ["dout", "out_int<0>", "out_int<1>", "bl", "br"]
        else:
            return ["dout", "out_int", "outb_int", "bl", "br"]

    def probe_bank(self, bank):
        super().probe_bank(bank)

        self.probe_labels.add("Xsram.Xbank{}.read_buf".format(bank))
        self.probe_labels.add("Xsram.Xbank{}.bank_sel_buf".format(bank))

        # predecoder flop output
        if OPTS.use_pex:
            decoder = self.sram.bank.decoder
            for i in range(len(decoder.pre2x4_inst) + len(decoder.pre3x8_inst)):
                pass
                self.probe_labels.add("Xsram.Xrow_decoder_Xpre_{}_in[0]".format(i))
                self.probe_labels.add("Xsram.Xrow_decoder_Xpre_{}_in[1]".format(i))
            self.probe_labels.add("Xsram.decoder_clk_Xrow_decoder")

        # sel outputs
        if self.sram.words_per_row > 1 and OPTS.verbose_save:
            for i in range(self.sram.words_per_row):
                if OPTS.use_pex:
                    col = (self.word_size - 1) * self.sram.words_per_row + i
                    self.probe_labels.add("Xsram.sel[{0}]_Xbank{1}_Xcolumn_mux_array_xmod_{2}".
                                          format(i, bank, col))
                else:
                    self.probe_labels.add("Xsram.sel[{}]".format(bank, i))

    def add_decoder_inputs(self, address):
        if not OPTS.push:
            return
        # get logic input node names
        decoder = self.sram.bank.decoder
        and_gate_index = int(address / 2)
        nand_inst = decoder.and_insts[and_gate_index]
        decoder_conn = decoder.conns[decoder.insts.index(nand_inst)]
        enable_index = decoder_conn.index("en")
        logic_inputs = decoder_conn[:enable_index]
        # get hierarchy of module names
        labels = []
        for node_name in logic_inputs:
            if OPTS.use_pex:
                labels.append("Xsram.Xrow_decoder_{}_Xrow_decoder_X{}".format(node_name, nand_inst.name))
            else:
                labels.append("Xsram.Xrow_decoder.{}".format(node_name))
        self.probe_labels.update(labels)
        self.decoder_inputs_probes[address] = labels

    def probe_address(self, address, pin_name="q"):

        address = self.address_to_vector(address)
        address_int = self.address_to_int(address)

        bank_index, bank_inst, row, col_index = self.decode_address(address)

        decoder_label = "Xsram.dec_out[{}]".format(row)
        self.decoder_probes[address_int] = decoder_label
        self.probe_labels.add(decoder_label)

        self.add_decoder_inputs(address_int)

        col = self.sram.num_cols - 1
        wl_label = self.get_wordline_label(bank_index, row, col)
        if self.two_bank_dependent:
            self.probe_labels.add(wl_label)
            wl_label = self.get_wordline_label(1, row, col)

        self.voltage_probes["wl"][address_int] = wl_label
        self.probe_labels.add(wl_label)

        pin_labels = [""] * self.sram.word_size
        for bit in range(self.word_size):
            col = bit * self.sram.words_per_row + col_index
            pin_labels[bit] = self.get_bitcell_label(bank_index, row, col, pin_name)
            if self.two_bank_dependent:
                pin_labels[bit + self.word_size] = self.get_bitcell_label(1, row,
                                                                          col, pin_name)

        if not OPTS.mram or not OPTS.use_pex:
            self.probe_labels.update(pin_labels)
        self.state_probes[address_int] = pin_labels

    def extract_probes(self):
        """Extract probes from extracted pex file"""
        super().extract_probes()

    def extract_from_pex(self, label: str, pex_file=None):
        if label.startswith("Xbitcell_b"):
            return label
        return super().extract_from_pex(label, pex_file)
