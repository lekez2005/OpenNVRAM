from subprocess import CalledProcessError, check_output

import debug
from characterizer.sram_probe import SramProbe
from globals import OPTS


class SharedProbe(SramProbe):
    """
    Adds probe labels to the sram such that the label names are partially retained post extraction
    The actual post extraction label is obtained using regex
    """

    def __init__(self, sram, pex_file=None):
        super().__init__(sram, pex_file)

        self.state_probes = {}
        self.sense_amp_probes = {}
        self.decoder_probes = {}
        self.dout_probes = {}
        self.mask_probes = {}
        for i in range(sram.word_size):
            self.dout_probes[i] = "D[{}]".format(i)
            self.mask_probes[i] = "mask[{}]".format(i)

        self.clk_buf_probe = "clk"
        self.current_probes = set()

    def get_buffer_probes(self, buf):
        results = []
        buffer_mod = getattr(buf, "buffer_mod", buf)
        num_stages = len(buffer_mod.buffer_invs)
        if hasattr(buf, "buffer_mod"):
            prefix = "_Xbuffer"
        else:
            prefix = ""

        for i in range(2):
            inverter_index = num_stages - i - 1
            num_fingers = buffer_mod.buffer_invs[inverter_index].tx_mults
            for fing in range(num_fingers):
                if fing == 0:
                    results.append("{}_Xinv{}_Mpinv_pmos:d".format(prefix, inverter_index))
                else:
                    results.append("{}_Xinv{}_Mpinv_pmos__{}:d".format(prefix, inverter_index, fing + 1))
        return results

    def probe_bank_currents(self, bank):
        if not OPTS.verbose_save:
            return

        if OPTS.use_pex:
            for col in range(self.sram.word_size):
                # write drivers
                self.current_probes.add("Xsram.XXbank{}_Xwrite_driver_array_Xdriver_{}_MM4:d".
                                        format(bank, col))
                self.current_probes.add("Xsram.XXbank{}_Xwrite_driver_array_Xdriver_{}_MM12:d".
                                        format(bank, col))

                # sense amps
                if OPTS.baseline:
                    self.current_probes.add("Xsram.XXbank{}_Xsense_amp_array_Xsa_d{}_XI0_MM1:d".
                                            format(bank, col))
                    self.current_probes.add("Xsram.XXbank{}_Xsense_amp_array_Xsa_d{}_XI2_MM1:d".
                                            format(bank, col))
                else:
                    self.current_probes.add("Xsram.XXbank{}_Xsense_amp_array_Xsa_d{}_XI0_MM1:d".
                                            format(bank, col))
                    self.current_probes.add("Xsram.XXbank{}_Xsense_amp_array_Xsa_d{}_XI1_MM1:d".
                                            format(bank, col))
                    self.current_probes.add("Xsram.XXbank{}_Xsense_amp_array_Xsa_d{}_XI2_MM1:d".
                                            format(bank, col))
                    self.current_probes.add("Xsram.XXbank{}_Xsense_amp_array_Xsa_d{}_XI3_MM1:d".
                                            format(bank, col))

                # precharge
                self.current_probes.add("Xsram.XXbank{}_Xprecharge_array_Xpre_column_{}_Mbl_pmos:d".
                                        format(bank, col))
                self.current_probes.add("Xsram.XXbank{}_Xprecharge_array_Xpre_column_{}_Mbr_pmos:d".
                                        format(bank, col))

            insts = ["precharge_buf_inst", "clk_buf_inst", "wordline_buf_inst", "write_buf_inst", "sense_amp_buf_inst"]
            for inst in insts:
                buffer_inst = getattr(self.sram.bank.control_buffers, inst)
                self.current_probes.update(["Xsram.XXbank{}_Xcontrol_buffers_X{}".format(bank, buffer_inst.name) + x
                                            for x in self.get_buffer_probes(buffer_inst.mod)])

    def probe_address_currents(self, address):
        bank, _, _, col_index = self.decode_address(address)
        if OPTS.verbose_save:
            bits = list(range(self.sram.word_size))
        else:
            cols = OPTS.probe_cols
            bits = [int(x / self.sram.words_per_row) for x in cols]

        if OPTS.use_pex:
            for bit in bits:
                col = bit * self.sram.words_per_row + col_index
                # bitcells
                self.current_probes.add("Xsram.XXbank{}_Xbitcell_array_Xbit_r{}_c{}_M4:d".
                                        format(address, bank, col))
                self.current_probes.add("Xsram.XXbank{}_Xbitcell_array_Xbit_r{}_c{}_M5:d".
                                        format(address, bank, col))
                # wordlines
            self.current_probes.update(["Xsram.XXbank{}_Xwordline_driver_Xdriver{}".format(bank, address) +
                                        x for x in
                                        self.get_buffer_probes(self.sram.bank.wordline_driver.logic_buffer)])

    def probe_write_drivers(self, bank):
        """Probe write driver internal bl_bar, br_bar"""

        for bit in range(self.sram.word_size):
            col = int(bit * self.sram.words_per_row)
            if OPTS.verbose_save:
                # bl_bar and br_bar
                for pin_name in ["bl_bar", "br_bar"]:
                    pin_label = "Xsram.Xbank{}.Xwrite_driver_array.Xdriver_{}.{}". \
                        format(0, bit, pin_name)
                    self.probe_labels.add(pin_label)

                if OPTS.use_pex:
                    # clk_buf at flop in
                    self.probe_labels.add("Xsram.clk_bar_{b1}_Xbank{bank}_Xdata_in_Xdff{bit}".
                                          format(bank=bank, b1=bank + 1, bit=bit))
                    # write_en
                    self.probe_labels.add("Xsram.Xbank{bank}_write_en_Xbank{bank}_Xwrite_driver_array_Xdriver_{bit}".
                                          format(bank=bank, bit=bit))
                    self.probe_labels.add(
                        "Xsram.Xbank{bank}_write_en_bar_Xbank{bank}_Xwrite_driver_array_Xdriver_{bit}".
                            format(bank=bank, bit=bit))
                    # vdd
                    self.probe_labels.add("vdd_Xbank{bank}_Xwrite_driver_array_Xdriver_{bit}".
                                          format(bank=bank, bit=bit))

                    # sense_en
                    self.probe_labels.add("Xsram.Xbank{bank}_sense_en_Xbank{bank}_Xsense_amp_array_Xsa_d{bit}".
                                          format(bank=bank, bit=bit))
                    # precharge_en
                    self.probe_labels.add("Xsram.Xbank{bank}_precharge_en_bar_Xbank{bank}_Xprecharge_array"
                                          "_Xpre_column_{col}".format(bank=bank, col=col))

            # flop in
            if OPTS.use_pex:
                pin_label = "Xsram.Xbank{bank}_Xdata_in_Xdff{bit}_clk_bar".format(bank=bank, bit=bit)
                self.probe_labels.add(pin_label)

            if OPTS.verbose_save:
                # flop out
                if OPTS.use_pex:
                    pin_label = "Xsram.Xbank{bank}_data_in[{bit}]_Xbank{bank}_Xwrite_driver_array_Xdriver_{bit}". \
                        format(bank=bank, bit=bit)
                else:
                    pin_label = "Xsram.Xbank{bank}.data_in[{col}]".format(bank=bank, col=col)
                self.probe_labels.add(pin_label)

            # mask in
            if OPTS.use_pex:
                pin_label = "Xsram.Xbank{bank}_mask_in_bar[{bit}]_Xbank{bank}_Xwrite_driver_array_Xdriver_{bit}". \
                    format(bank=bank, bit=bit)
            else:
                pin_label = "Xsram.Xbank{bank}.mask_in_bar[{bit}]".format(bank=bank, bit=bit)
            self.probe_labels.add(pin_label)

    def probe_latched_sense_amps(self, bank):

        cols = range(self.sram.word_size) if OPTS.verbose_save else OPTS.probe_cols
        bits = [int(x / self.sram.words_per_row) for x in cols]

        for bit in bits:
            if OPTS.use_pex:
                self.probe_labels.add("Xbank{0}_Xsense_amp_array_Xsa_d{1}_outb_Xbank{0}_Xsense_amp_array".
                                      format(bank, bit))
                self.probe_labels.add("Xbank{0}_and_out[{1}]_Xbank{0}_Xsense_amp_array".format(bank, bit))
            else:
                self.probe_labels.add("Xsram.Xbank{0}.Xsense_amp_array.Xsa_d{1}.outb".format(bank, bit))
                self.probe_labels.add("Xsram.Xbank{0}.and_out[{1}]".format(bank, bit))

        if OPTS.use_pex:
            self.probe_labels.add("Xsram.Xbank{bank}_read_buf_Xbank{bank}_"
                                  "Xcontrol_buffers_Xsample_bar_int".format(bank=bank))
            self.probe_labels.add("Xbank{}_Xcontrol_buffers_sample_bar_int".format(bank))

    def probe_misc_bank(self, bank):

        # control buffers
        nets = {
            "wordline_en": "Xwordline_driver_Xdriver{row}",
            "precharge_en_bar": "Xprecharge_array_Xpre_column_{col}",
            "write_en": "Xwrite_driver_array_Xdriver_{bit}",
            "write_en_bar": "Xwrite_driver_array_Xdriver_{bit}",
            "sense_en": "Xsense_amp_array_Xsa_d{bit}",
            "sample_en_bar": "Xsense_amp_array_Xsa_d{bit}",
            "tri_en": "Xtri_gate_array_Xtri_gate{bit}",
            "tri_en_bar": "Xtri_gate_array_Xtri_gate{bit}"
        }

        if OPTS.verbose_save:
            bits = list(range(self.sram.word_size))
            cols = [x * self.sram.words_per_row for x in bits]
        else:
            cols = OPTS.probe_cols
            bits = [int(x / self.sram.words_per_row) for x in cols]
        row = self.sram.bank.num_rows - 1

        net_format = "Xsram.Xbank{bank}_{net}_Xbank{bank}_{net_location}"
        for net in nets:
            if OPTS.use_pex:
                self.probe_labels.add("Xsram.Xbank{bank}_{net}_Xbank{bank}_Xcontrol_buffers".
                                      format(bank=bank, net=net))
                for i in range(len(cols)):
                    bit = bits[i]
                    col = cols[i]
                    # control buffer outputs
                    probe_label = net_format.format(bank=bank, net=net,
                                                    net_location=nets[net].format(bit=bit, row=row,
                                                                                  col=col))
                    self.probe_labels.add(probe_label)
            else:
                probe_label = "Xsram.Xbank{}.{}".format(bank, net)
                self.probe_labels.add(probe_label)

        # bl_out
        if OPTS.use_pex and self.sram.words_per_row > 1:
            for bit in bits:
                self.probe_labels.add("Xsram.Xbank{0}_bl_out[{1}]_Xbank{0}_Xsense_amp_array".format(bank, bit))
                self.probe_labels.add("Xsram.Xbank{0}_br_out[{1}]_Xbank{0}_Xsense_amp_array".format(bank, bit))

        # clk_bar
        if OPTS.use_pex:
            for bit in bits:
                self.probe_labels.add("Xsram.clk_bar_{}_Xbank{}_Xdata_in_Xdff{}".format(bank + 1, bank, bit))
        else:
            self.probe_labels.add("Xsram.clk_bar_{}".format(bank + 1))

        if OPTS.use_pex:
            self.clk_buf_probe = "Xsram.clk_buf_{}_Xbank{}_Xcontrol_buffers".format(bank + 1, bank)
        else:
            self.clk_buf_probe = "Xsram.clk_buf_{}".format(bank + 1)

        for bit in bits:
            if OPTS.use_pex:
                if not OPTS.baseline:
                    # sense amp ref
                    self.probe_labels.add("sense_amp_ref_Xbank{bank}_Xsense_amp_array_Xsa_d{bit}".
                                          format(bank=bank, bit=bit))
                if OPTS.verbose_save:
                    # output of data_in flops
                    self.probe_labels.add(
                        "Xsram.Xbank{bank}_data_in[{bit}]_Xbank{bank}_Xdata_in".format(bank=bank, bit=bit))
            else:
                self.probe_labels.add("Xsram.Xbank{}.data_in[{}]".format(bank, bit))

        # internal control buffer
        labels = ["bank_sel_cbar", "sel_clk_sense"]

        for i in range(len(labels)):
            self.probe_labels.add("Xsram.Xbank{}.Xcontrol_buffers.{}".format(bank, labels[i]))

        for i in range(len(self.sram.bank.control_buffers.clk_buf.buffer_stages) - 2):
            if OPTS.use_pex:
                self.probe_labels.add("Xbank{}.Xcontrol_buffers.Xclk_buf.Xbuffer.out_{}".format(bank, i + 1))
            else:
                self.probe_labels.add("Xsram.Xbank{}.Xcontrol_buffers.Xclk_buf.Xbuffer.out_{}".format(bank, i + 1))

        # predecoder flop output
        if OPTS.use_pex:
            self.probe_labels.add("Xsram.Xrow_decoder_Xpre[0]_in[0]")
            self.probe_labels.add("Xsram.clk_buf_1_Xrow_decoder")

        # sel outputs
        if self.sram.words_per_row > 0 and OPTS.verbose_save:
            for i in range(self.sram.words_per_row):
                if OPTS.use_pex:
                    col = (self.sram.word_size - 1) * self.sram.words_per_row + i
                    self.probe_labels.add("Xsram.sel[{0}]_Xbank{1}_Xcolumn_mux_array_XMUX{2}".
                                          format(i, bank, col))
                else:
                    self.probe_labels.add("Xsram.sel[{}]".format(bank, i))

    def probe_address(self, address, pin_name="Q"):

        address = self.address_to_vector(address)
        address_int = self.address_to_int(address)

        bank_index, bank_inst, row, col_index = self.decode_address(address)

        decoder_label = "Xsram.dec_out[{}]".format(row)
        self.decoder_probes[address_int] = decoder_label
        self.probe_labels.add(decoder_label)

        col = self.sram.num_cols - 1
        wl_label = self.get_wordline_label(bank_index, row, col)

        self.wordline_probes[address_int] = wl_label
        self.probe_labels.add(wl_label)

        pin_labels = [""] * self.sram.word_size
        for bit in range(self.sram.word_size):
            col = bit * self.sram.words_per_row + col_index
            pin_labels[bit] = self.get_bitcell_label(bank_index, row, col, pin_name)

        self.probe_labels.update(pin_labels)
        self.state_probes[address_int] = pin_labels

    def extract_probes(self):
        """Extract probes from extracted pex file"""
        if OPTS.use_pex:
            debug.info(1, "Extracting probes")
            self.saved_nodes = set()
            for label in self.probe_labels:
                try:
                    extracted = self.extract_from_pex(label)
                    self.saved_nodes.add(extracted)
                    debug.info(2, "Probe for label {} = {}".format(label, extracted))
                except CalledProcessError:
                    debug.warning("Probe {} not found in extracted netlist".format(label))
            try:
                bus_probes = [self.bitline_probes, self.br_probes, self.decoder_probes]
                for bus_probe in bus_probes:
                    if bus_probe == self.dout_probes and OPTS.baseline:
                        continue
                    for bit, label in bus_probe.items():
                        bus_probe[bit] = self.extract_from_pex(label)
                for address, address_labels in self.state_probes.items():
                    self.state_probes[address] = [self.extract_from_pex(address_label)
                                                  for address_label in address_labels]
                self.clk_buf_probe = self.extract_from_pex(self.clk_buf_probe)
            except CalledProcessError:  # ignore missing probe errors
                pass
            debug.info(1, "Done Extracting probes")
        else:
            self.saved_nodes = set(self.probe_labels)

    def extract_from_pex(self, label, pex_file=None):

        prefix = "Xsram."
        if pex_file is None:
            pex_file = self.pex_file
        match = None
        try:
            label_sub = label.replace(prefix, "").replace(".", "_") \
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
