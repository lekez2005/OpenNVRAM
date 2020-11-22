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
        debug.info(1, "Initialize sram probe")
        self.two_bank_push = OPTS.push and self.sram.num_banks == 2
        self.is_cmos = OPTS.baseline or OPTS.push

        self.state_probes = {}
        self.sense_amp_probes = {}
        self.decoder_probes = {}
        self.decoder_inputs_probes = {}
        self.dout_probes = {}
        self.mask_probes = {}
        self.wwl_probes = {}
        for i in range(sram.word_size):
            self.dout_probes[i] = "D[{}]".format(i)
            self.mask_probes[i] = "mask[{}]".format(i)

        self.clk_buf_probe = "clk"
        self.current_probes = set()

    def get_bitcell_label(self, bank_index, row, col, pin_name):
        if self.is_cmos or not OPTS.use_pex:
            if not self.is_cmos:
                pin_name = "state"
            return "Xsram.Xbank{}.Xbitcell_array.Xbit_r{}_c{}.{}".format(
                bank_index, row, col, pin_name)
        else:
            bitcell_name = OPTS.bitcell_name_template.format(bank=bank_index, row=row, col=col)
            return bitcell_name + ".state"

    def get_storage_node_pattern(self):
        if self.is_cmos or not OPTS.use_pex:
            pattern = super().get_storage_node_pattern()
        else:
            pattern = OPTS.bitcell_name_template + ".state"
        debug.info(2, "Storage node pattern = {}".format(pattern))
        return pattern

    def get_w_label(self, bank_index, row, col):
        if OPTS.use_pex:
            wl_label = "Xsram.Xbank{bank}.wl[{row}]_Xbank{bank}" \
                       "_Xbitcell_array_Xbit_r{row}_c{col}".format(bank=bank_index, row=row, col=col)
        else:
            wl_label = "Xsram.Xbank{}.wl[{}]".format(bank_index, row)
        return wl_label

    def get_wordline_label(self, bank_index, row, col):
        w_label = self.get_w_label(bank_index, row, col)
        if not (OPTS.baseline or OPTS.push):
            w_label = w_label.replace("wl", "rwl")
        return w_label

    def get_wwl_label(self, bank_index, row, col):
        return self.get_w_label(bank_index, row, col).replace("wl", "wwl")

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
                    results.append("{}_Xinv{}_Mpinv_pmos@{}:d".format(prefix, inverter_index, fing + 1))
        return results

    def probe_bank_currents(self, bank):
        if not OPTS.verbose_save:
            return

        if OPTS.use_pex and not OPTS.push:
            for col in range(self.sram.word_size):
                # write drivers
                self.current_probes.add("Xsram.XXbank{}_Xwrite_driver_array_Xdriver_{}_mm4:d".
                                        format(bank, col))
                self.current_probes.add("Xsram.XXbank{}_Xwrite_driver_array_Xdriver_{}_mm12:d".
                                        format(bank, col))

                # sense amps
                if OPTS.baseline:
                    self.current_probes.add("Xsram.XXbank{}_Xsense_amp_array_Xsa_d{}_XI0_mm1:d".
                                            format(bank, col))
                    self.current_probes.add("Xsram.XXbank{}_Xsense_amp_array_Xsa_d{}_XI2_mm1:d".
                                            format(bank, col))
                else:
                    self.current_probes.add("Xsram.XXbank{}_Xsense_amp_array_Xsa_d{}_XI0_mm1:d".
                                            format(bank, col))
                    self.current_probes.add("Xsram.XXbank{}_Xsense_amp_array_Xsa_d{}_XI2_mm1:d".
                                            format(bank, col))

                # precharge
                self.current_probes.add("Xsram.XXbank{}_Xprecharge_array_Xpre_column_{}_Mbl_pmos:d".
                                        format(bank, col))
                if OPTS.baseline:
                    self.current_probes.add(
                        "Xsram.XXbank{}_Xprecharge_array_Xpre_column_{}_Mbr_pmos:d".
                            format(bank, col))

            insts = ["precharge_buf_inst", "clk_buf_inst", "write_buf_inst", "sense_amp_buf_inst"]
            if OPTS.baseline or (OPTS.push and bank == 0):
                insts.append("wordline_buf_inst")
            else:
                insts.extend(["wwl_en_inst", "rwl_buf_inst"])
            for inst in insts:
                buffer_inst = getattr(self.sram.bank.control_buffers, inst)
                self.current_probes.update(["Xsram.Xbank{}_Xcontrol_buffers_X{}".format(bank, buffer_inst.name) + x
                                            for x in self.get_buffer_probes(buffer_inst.mod)])

    def probe_address_currents(self, address):
        bank, _, row, col_index = self.decode_address(address)
        if OPTS.verbose_save:
            bits = list(range(self.sram.word_size))
        else:
            cols = OPTS.probe_cols
            bits = [int(x / self.sram.words_per_row) for x in cols]

        for bit in bits:
            col = bit * self.sram.words_per_row + col_index
            if OPTS.use_pex and self.is_cmos:
                prefix = "X" if OPTS.baseline else "m"
                # bitcells
                self.current_probes.add("Xsram.{}Xbank{}_Xbitcell_array_Xbit_r{}_c{}_m4:d".
                                        format(prefix, bank, row, col))
                self.current_probes.add("Xsram.{}Xbank{}_Xbitcell_array_Xbit_r{}_c{}_m5:d".
                                        format(prefix, bank, row, col))
            elif OPTS.use_pex:
                bitcell_name = OPTS.bitcell_name_template.format(bank=bank, row=row, col=col)
                self.current_probes.add(bitcell_name + ".m1:d")
            else:
                self.current_probes.add("Xsram.Xbank{}.Xbitcell_array.Xbit_r{}_c{}.{}".format(
                    bank, row, col, "m1:d"
                ))
            # wordlines
            if OPTS.verbose_save and OPTS.use_pex:
                template = "Xsram.Xbank{}_Xwordline_driver_Xdriver{}"
                if not OPTS.baseline:
                    template = template.replace("wordline_driver", "wwl_driver")
                driver_probes = [template.format(bank, row) + x for x in
                                 self.get_buffer_probes(
                                     self.sram.bank.wordline_driver.logic_buffer)]
                self.current_probes.update(driver_probes)
            # if OPTS.mram == "sotfet" and OPTS.verbose_save:
            #     # save write currents
            #     if OPTS.use_pex:
            #         self.current_probes.add("Xsram.Xbank{}_Xbitcell_array_Xbit_r{}_c{}_M1:d".
            #                                 format(bank, row, col))
            #     else:
            #         self.current_probes.add("Xsram.Xbank{}.Xbitcell_array.Xbit_r{}_c{}.M1:d".
            #                                 format(bank, row, col))

    def probe_write_drivers(self, bank):
        """Probe write driver internal bl_bar, br_bar"""

        for bit in range(self.sram.word_size):
            if OPTS.verbose_save:
                # bl_bar and br_bar
                if OPTS.push:
                    pin_names = ["Xchild_mod.bl_p", "Xchild_mod.bl_n", "Xchild_mod.mask_en"]
                else:
                    pin_names = ["bl_bar", "br_bar"]
                for pin_name in pin_names:
                    pin_label = "Xsram.Xbank{}.Xwrite_driver_array.Xdriver_{}.{}". \
                        format(0, bit, pin_name)
                    self.probe_labels.add(pin_label)

                if OPTS.use_pex:
                    # vdd
                    self.probe_labels.add("vdd_Xbank{bank}_Xwrite_driver_array_Xdriver_{bit}".
                                          format(bank=bank, bit=bit))

            # flop clk_bar
            if OPTS.use_pex:
                if OPTS.push:
                    i_range = range(0) if bit % 2 == 1 else range(2)
                    for i in i_range:
                        self.probe_labels.add("Xsram.Xbank{}_Xdata_in_Xdff{}"
                                              "_Xchild_mod_xi0<{}>_clk_bar".format(bank, int(bit / 2), i))
                else:
                    pin_label = "Xsram.Xbank{bank}_Xdata_in_Xdff{bit}_clk_bar".format(bank=bank, bit=bit)
                    self.probe_labels.add(pin_label)

            if OPTS.verbose_save:
                # flop out
                if OPTS.use_pex:
                    pin_label = "Xsram.Xbank{bank}_data_in[{bit}]_Xbank{bank}_Xwrite_driver_array_Xdriver_{bit}". \
                        format(bank=bank, bit=bit)
                else:
                    pin_label = "Xsram.Xbank{bank}.data_in[{bit}]".format(bank=bank, bit=bit)
                self.probe_labels.add(pin_label)

            # mask in
            if OPTS.push:
                mask_net = "mask_in"
            else:
                mask_net = "mask_in_bar"
            if OPTS.use_pex:
                pin_label = "Xsram.Xbank{bank}_{net}[{bit}]_Xbank{bank}_Xwrite_driver_array_Xdriver_{bit}". \
                    format(bank=bank, bit=bit, net=mask_net)
            else:
                pin_label = "Xsram.Xbank{bank}.{net}[{bit}]".format(bank=bank, bit=bit, net=mask_net)
            self.probe_labels.add(pin_label)

    def probe_latched_sense_amps(self, bank):

        if OPTS.verbose_save:
            bits = list(range(self.sram.word_size))
        else:
            cols = OPTS.probe_cols
            bits = [int(x / self.sram.words_per_row) for x in cols]

        for bit in bits:
            if self.sram.bank.mirror_sense_amp:
                continue
            if OPTS.use_pex and not OPTS.push:
                self.probe_labels.add("Xbank{0}_Xsense_amp_array_Xsa_d{1}_out_int_Xbank{0}_Xsense_amp_array".
                                      format(bank, bit))
                self.probe_labels.add("Xbank{0}_Xsense_amp_array_Xsa_d{1}_outb_int_Xbank{0}_Xsense_amp_array".
                                      format(bank, bit))
                self.probe_labels.add("Xbank{0}_and_out[{1}]_Xbank{0}_Xsense_amp_array".format(bank, bit))
            elif OPTS.use_pex and OPTS.push:
                if bit % 2 == 1:
                    continue

                child_mod = "Xbank{}_Xsense_amp_array_Xsa_d{}_Xchild_mod".format(bank, int(bit / 2))
                for i in range(2):
                    self.probe_labels.add("{0}_out_int<{1}>_{0}".format(child_mod, i))
            else:
                self.probe_labels.add("Xsram.Xbank{0}.Xsense_amp_array.Xsa_d{1}.out_int".format(bank, bit))
                self.probe_labels.add("Xsram.Xbank{0}.and_out[{1}]".format(bank, bit))

        if OPTS.use_pex and OPTS.baseline:
            self.probe_labels.add("Xsram.Xbank{bank}_read_buf_Xbank{bank}_"
                                  "Xcontrol_buffers_Xsample_bar_int".format(bank=bank))
            self.probe_labels.add("Xbank{}_Xcontrol_buffers_sample_bar_int".format(bank))

    def probe_clk_buf(self, bank):
        if OPTS.use_pex:
            self.clk_buf_probe = "Xsram.clk_buf_{}_Xbank{}_Xcontrol_buffers".format(bank + 1, bank)
        else:
            self.clk_buf_probe = "Xsram.clk_buf_{}".format(bank + 1)

    def probe_misc_bank(self, bank):

        # control buffers
        nets = {
            "precharge_en_bar": "Xprecharge_array_Xpre_column_{col}",
            "write_en": "Xwrite_driver_array_Xdriver_{bit}",
            "sense_en": "Xsense_amp_array_Xsa_d{bit}",
            "tri_en": "Xtri_gate_array_Xtri_gate{bit}"
        }
        if not OPTS.push:
            nets["tri_en_bar"] = "Xtri_gate_array_Xtri_gate{bit}"
            nets["write_en_bar"] = "Xwrite_driver_array_Xdriver_{bit}"

        if not self.sram.bank.mirror_sense_amp:
            nets["sample_en_bar"] = "Xsense_amp_array_Xsa_d{bit}"
        if OPTS.baseline:
            nets["wordline_en"] = "Xwordline_driver_Xdriver{row}"
        elif OPTS.push:
            pass
        else:
            nets["rwl_en"] = "Xrwl_driver_Xdriver{row}"
            nets["wwl_en"] = "Xwwl_driver_Xdriver{row}"
            nets["br_reset"] = "Xsense_amp_array_Xsa_d{bit}"

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
                    if OPTS.push:
                        if "write_driver_array" not in nets[net]:
                            if bit % 2 == 1:
                                continue
                            bit = int(bit / 2)
                    # control buffer outputs
                    probe_label = net_format.format(bank=bank, net=net,
                                                    net_location=nets[net].format(bit=bit, row=row,
                                                                                  col=col))
                    self.probe_labels.add(probe_label)
            else:
                probe_label = "Xsram.Xbank{}.{}".format(bank, net)
                self.probe_labels.add(probe_label)
        # push wordline_en
        if OPTS.push and bank == 0:
            if OPTS.use_pex:
                self.probe_labels.add("wordline_en_Xbank0_Xcontrol_buffers")
                self.probe_labels.add("wordline_en_Xrow_decoder_Xand_{}".format(0))
                self.probe_labels.add("wordline_en_Xrow_decoder_Xand_{}".format(int(self.sram.bank.num_rows / 2) - 2))
            else:
                self.probe_labels.add("Xsram.wordline_en")

        # bl_out
        if OPTS.use_pex and self.sram.words_per_row > 1:
            for bit in bits:
                self.probe_labels.add("Xsram.Xbank{0}_bl_out[{1}]_Xbank{0}_Xsense_amp_array".format(bank, bit))
                self.probe_labels.add("Xsram.Xbank{0}_br_out[{1}]_Xbank{0}_Xsense_amp_array".format(bank, bit))

        # clk_bar
        if OPTS.use_pex:
            for bit in bits:
                if OPTS.push:
                    if bit % 2 == 1:
                        continue
                    for i in range(2):
                        self.probe_labels.add("Xsram.clk_bar_{}_Xbank{}_Xdata_in"
                                              "_Xdff{}_Xchild_mod_xi0<{}>".
                                              format(bank + 1, bank, int(bit / 2), i))
                else:
                    self.probe_labels.add("Xsram.clk_bar_{}_Xbank{}_Xdata_in_Xdff{}".format(bank + 1, bank, bit))
        else:
            self.probe_labels.add("Xsram.clk_bar_{}".format(bank + 1))

        self.probe_clk_buf(bank)

        for bit in bits:
            if OPTS.use_pex:
                if not OPTS.baseline and not OPTS.push:
                    # sense amp ref
                    self.probe_labels.add("vref_Xbank{bank}_Xsense_amp_array_Xsa_d{bit}".
                                          format(bank=bank, bit=bit))
                if OPTS.verbose_save:
                    # output of data_in flops
                    self.probe_labels.add(
                        "Xsram.Xbank{bank}_data_in[{bit}]_Xbank{bank}_Xdata_in".format(bank=bank, bit=bit))
            else:
                self.probe_labels.add("Xsram.Xbank{}.data_in[{}]".format(bank, bit))

        if OPTS.baseline:
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
            decoder = self.sram.bank.decoder
            for i in range(len(decoder.pre2x4_inst) + len(decoder.pre3x8_inst)):
                pass
                self.probe_labels.add("Xsram.Xrow_decoder_Xpre_{}_in[0]".format(i))
                self.probe_labels.add("Xsram.Xrow_decoder_Xpre_{}_in[1]".format(i))
            self.probe_labels.add("Xsram.clk_buf_1_Xrow_decoder")

        # sel outputs
        if self.sram.words_per_row > 1 and OPTS.verbose_save:
            for i in range(self.sram.words_per_row):
                if OPTS.use_pex:
                    col = (self.sram.word_size - 1) * self.sram.words_per_row + i
                    self.probe_labels.add("Xsram.sel[{0}]_Xbank{1}_Xcolumn_mux_array_XMUX{2}".
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
        if not self.is_cmos:
            self.wwl_probes[address_int] = self.get_wwl_label(bank_index, row, col)
            self.probe_labels.add(self.wwl_probes[address_int])

        self.wordline_probes[address_int] = wl_label
        self.probe_labels.add(wl_label)

        full_word_size = 2 * self.sram.word_size if self.two_bank_push else self.sram.word_size
        pin_labels = [""] * full_word_size
        for bit in range(self.sram.word_size):
            col = bit * self.sram.words_per_row + col_index
            pin_labels[bit] = self.get_bitcell_label(bank_index, row, col, pin_name)
            if self.two_bank_push:
                pin_labels[bit + self.sram.word_size] = self.get_bitcell_label(1, row, col, pin_name)

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
                bus_probes = [self.bitline_probes, self.br_probes, self.decoder_probes,
                              self.wwl_probes, self.wordline_probes]
                for bus_probe in bus_probes:
                    if bus_probe == self.dout_probes and OPTS.baseline:
                        continue
                    for bit, label in bus_probe.items():
                        bus_probe[bit] = self.extract_from_pex(label)
                for address, address_labels in self.state_probes.items():
                    self.state_probes[address] = [self.extract_from_pex(address_label)
                                                  for address_label in address_labels]
                for _, val in self.decoder_inputs_probes.items():
                    for i in range(len(val)):
                        val[i] = self.extract_from_pex(val[i])
                self.clk_buf_probe = self.extract_from_pex(self.clk_buf_probe)
            except CalledProcessError:  # ignore missing probe errors
                pass
            debug.info(1, "Done Extracting probes")
        else:
            self.saved_nodes = set(self.probe_labels)

    def extract_from_pex(self, label: str, pex_file=None):
        if label.startswith("Xbitcell_b"):
            return label

        prefix = "Xsram."
        if pex_file is None:
            pex_file = self.pex_file
        match = None
        try:
            label_sub = label.replace(prefix, "").replace(".", "_") \
                .replace("[", "\[").replace("]", "\]")
            pattern = "\sN_{}_[MXmx]\S+_[gsd]".format(label_sub)
            match = check_output(["grep", "-m1", "-o", "-E", pattern, pex_file])

        except CalledProcessError as ex:
            if ex.returncode == 1:  # mismatch
                try:
                    # lvs box pins have exact match without mangling so search for exact match without regex
                    match = check_output(["grep", "-m1", "-Fo", label, pex_file])
                except CalledProcessError as ex:
                    if ex.returncode == 1:
                        # breakpoint()
                        debug.error("Match not found in pex file for label {} {}".format(label, pattern))
                        raise ex
                    else:
                        raise ex
            else:
                raise ex
        return 'Xsram.' + match.decode().strip()
