import os
from subprocess import CalledProcessError, check_output

import debug
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
        self.mask_probes = {}
        self.br_probes = {}
        self.clk_buf_probe = "clk"
        self.current_probes = set()

    def probe_bitlines(self, bank):
        row = self.sram.num_rows - 1
        for col in range(self.sram.num_cols):
            for pin_name in ["bl", "br"]:
                if OPTS.use_pex:  # select top right bitcell
                    pin_label = "Xsram.Xbank{bank}_{pin_name}[{col}]_Xbank{bank}_Xbitcell_array" \
                                "_Xbit_r{row}_c{col}".format(bank=bank, col=col, pin_name=pin_name, row=row)
                else:
                    pin_label = "Xsram.Xbank{}.{}[{}]".format(bank, pin_name, col)
                self.probe_labels.add(pin_label)
                if pin_name == "bl":
                    self.bitline_probes[col] = pin_label
                else:
                    self.br_probes[col] = pin_label

    def probe_alu(self):
        if OPTS.baseline:
            return
        if OPTS.use_pex:

            for col in range(self.sram.num_cols):
                if OPTS.serial:
                    self.probe_labels.add("Xalu_cin[{0}]_Xalu_Xmcc{0}".format(col))
                    self.probe_labels.add("Xalu_cout[{0}]_Xalu_Xmcc{0}".format(col))
                else:
                    self.probe_labels.add("Xalu_shift_out[{0}]_Xalu_Xmcc{0}".format(col))

                    if not col % 32 == 31:
                        if col % 2 == 0:
                            carry = "coutb_int[{}]".format(col)
                        else:
                            carry = "cout_int[{}]".format(col)
                        self.probe_labels.add("Xalu_{0}_Xalu_Xmcc{1}".format(carry, col))

                    self.probe_labels.add("Xalu_Xmcc{0}_XI8_net1_Xalu_Xmcc{0}".format(col))
            self.probe_labels.add("Xsram.Xalu.sr_clk_buf")

        if not OPTS.use_pex:
            if OPTS.serial:
                for i in range(self.sram.num_cols):
                    self.probe_labels.add("Xsram.Xalu.cout[{}]".format(i))
                    self.probe_labels.add("Xsram.Xalu.cin[{}]".format(i))
            else:
                for i in range(self.sram.num_cols):
                    self.probe_labels.add("Xsram.Xalu.shift_out[{}]".format(i))
                    self.probe_labels.add("Xsram.Xalu.bus_out[{}]".format(i))

    def probe_currents(self, addresses):

        def get_buffer_probes(buf):
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
                        results.append("{}_Xinv{}_Mpinv_pmos__{}:d".format(prefix, inverter_index, fing+1))
            return results

        if OPTS.use_pex:
            for col in range(self.sram.num_cols):
                # write drivers
                self.current_probes.add("Xsram.mXbank0_Xwrite_driver_array_Xdriver_{}_MM4:d".format(col))
                self.current_probes.add("Xsram.mXbank0_Xwrite_driver_array_Xdriver_{}_MM12:d".format(col))

                # sense amps
                if OPTS.baseline:
                    self.current_probes.add("Xsram.mXbank0_Xsense_amp_array_Xsa_d{}_XI0_MM1:d".format(col))
                    self.current_probes.add("Xsram.mXbank0_Xsense_amp_array_Xsa_d{}_XI2_MM1:d".format(col))
                else:
                    self.current_probes.add("Xsram.mXbank0_Xsense_amp_array_Xsa_d{}_XI0_MM1:d".format(col))
                    self.current_probes.add("Xsram.mXbank0_Xsense_amp_array_Xsa_d{}_XI1_MM1:d".format(col))
                    self.current_probes.add("Xsram.mXbank0_Xsense_amp_array_Xsa_d{}_XI2_MM1:d".format(col))
                    self.current_probes.add("Xsram.mXbank0_Xsense_amp_array_Xsa_d{}_XI3_MM1:d".format(col))

                # precharge
                self.current_probes.add("Xsram.mXbank0_Xprecharge_array_Xpre_column_{}_Mbl_pmos:d".format(col))
                self.current_probes.add("Xsram.mXbank0_Xprecharge_array_Xpre_column_{}_Mbr_pmos:d".format(col))

                # bitcells
                for ad in addresses:
                    self.current_probes.add("Xsram.mXbank0_Xbitcell_array_Xbit_r{}_c{}_M4:d".format(ad, col))
                    self.current_probes.add("Xsram.mXbank0_Xbitcell_array_Xbit_r{}_c{}_M5:d".format(ad, col))

            # wordlines
            for ad in addresses:
                self.current_probes.update(["Xsram.mXbank0_Xwordline_driver_Xdriver{}".format(ad) + x
                                            for x in get_buffer_probes(self.sram.bank.wordline_driver.logic_buffer)])

            insts = ["precharge_buf_inst", "clk_buf_inst", "wordline_buf_inst", "write_buf_inst", "sense_amp_buf_inst"]
            for inst in insts:
                buffer_inst = getattr(self.sram.bank.control_buffers, inst)
                self.current_probes.update(["Xsram.mXbank0_Xcontrol_buffers_X{}".format(buffer_inst.name) + x
                                            for x in get_buffer_probes(buffer_inst.mod)])

    def probe_write_drivers(self):
        """Probe write driver internal bl_bar, br_bar"""

        for col in range(self.sram.num_cols):
            # bl_bar and br_bar
            for pin_name in ["bl_bar", "br_bar"]:
                pin_label = "Xsram.Xbank{}.Xwrite_driver_array.Xdriver_{}.{}".\
                    format(0, col, pin_name)
                self.probe_labels.add(pin_label)

            if OPTS.use_pex:
                # clk_buf at flop in
                self.probe_labels.add("Xsram.Xbank{bank}_clk_bar_Xbank{bank}_Xdata_in_XXdff{col}".
                                      format(bank=0, col=col))
                # write_en
                self.probe_labels.add("Xsram.Xbank{bank}_write_en_Xbank{bank}_Xwrite_driver_array_Xdriver_{col}".
                                      format(bank=0, col=col))
                self.probe_labels.add("Xsram.Xbank{bank}_write_en_bar_Xbank{bank}_Xwrite_driver_array_Xdriver_{col}".
                                      format(bank=0, col=col))
                # vdd
                self.probe_labels.add("vdd_Xbank{bank}_Xwrite_driver_array_Xdriver_{col}".
                                      format(bank=0, col=col))

                # sense_en
                self.probe_labels.add("Xsram.Xbank{bank}_sense_en_Xbank{bank}_Xsense_amp_array_Xsa_d{col}".
                                      format(bank=0, col=col))
                # precharge_en
                self.probe_labels.add("Xsram.Xbank{bank}_precharge_en_bar_Xbank{bank}_Xprecharge_array"
                                      "_Xpre_column_{col}".format(bank=0, col=col))

            # flop in
            if OPTS.use_pex:
                if OPTS.baseline:
                    pin_label = "DATA[{col}]_Xbank{bank}_Xdata_in_XXdff{col}".format(bank=0, col=col)
                else:
                    pin_label = "bus[{col}]_Xbank{bank}_Xdata_in_XXdff{col}". \
                        format(bank=0, col=col)
            else:
                if OPTS.baseline:
                    self.probe_labels.add("Xsram.Xbank{bank}.and_out[{col}]".format(bank=0, col=col))
                pin_label = "Xsram.Xbank{bank}.DATA[{col}]".format(bank=0, col=col)
            self.probe_labels.add(pin_label)

            # flop out
            if OPTS.use_pex:
                pin_label = "Xsram.Xbank{bank}_data_in[{col}]_Xbank{bank}_Xwrite_driver_array_Xdriver_{col}". \
                    format(bank=0, col=col)
            else:
                pin_label = "Xsram.Xbank{bank}.data_in[{col}]".format(bank=0, col=col)
            self.probe_labels.add(pin_label)

            # mask in
            if OPTS.use_pex:
                if OPTS.baseline:
                    pin_label = "Xsram.Xbank{bank}_mask_in_bar[{col}]_Xbank{bank}_Xwrite_driver_array_Xdriver_{col}". \
                        format(bank=0, col=col)
                else:
                    pin_label = "mask_bar[{col}]_Xbank{bank}_Xwrite_driver_array_Xdriver_{col}". \
                        format(bank=0, col=col)
            else:
                pin_label = "Xsram.Xbank{bank}.mask_in_bar[{col}]".format(bank=0, col=col)
            self.probe_labels.add(pin_label)

    def probe_misc_bank(self, bank):

        # control buffers
        nets = {
            "clk_bar": "Xdata_in_XXdff{col}",
            "wordline_en": "Xwordline_driver_Xdriver{row}",
            "precharge_en_bar": "Xprecharge_array_Xpre_column_{col}",
            "write_en": "Xwrite_driver_array_Xdriver_{col}",
            "write_en_bar": "Xwrite_driver_array_Xdriver_{col}",
            "sense_en": "Xsense_amp_array_Xsa_d{col}",
            "sample_en_bar": "Xsense_amp_array_Xsa_d{col}"
        }

        row = self.sram.num_rows - 1
        cols = [0, int(self.sram.num_cols/2), self.sram.num_cols-1]

        for col in cols:

            destination_format = "Xsram.Xbank{bank}_{net}_Xbank{bank}_{net_location}"
            origin_format = "Xsram.Xbank{bank}_{net}_Xbank{bank}_Xcontrol_buffers"

            for net in nets:
                if OPTS.use_pex:
                    probe_label = destination_format.format(bank=bank, net=net,
                                                            net_location=nets[net].format(col=col, row=row))
                    self.probe_labels.add(probe_label)
                    probe_label = origin_format.format(bank=bank, net=net)
                    self.probe_labels.add(probe_label)
                else:
                    probe_label = "Xsram.Xbank{}.{}".format(bank, net)
                    self.probe_labels.add(probe_label)

        if OPTS.use_pex:
            if OPTS.baseline:
                self.clk_buf_probe = "Xsram.Xbank{bank}_clk_buf_Xbank{bank}_Xcontrol_buffers".format(bank=bank)
            else:
                self.clk_buf_probe = "clk_buf_Xbank{bank}_Xcontrol_buffers".format(bank=bank)
        else:
            self.clk_buf_probe = "Xsram.Xbank{}.clk_buf".format(bank)

        # output of data_in flops
        for col in cols:
            if OPTS.use_pex:
                self.probe_labels.add("Xsram.Xbank{bank}_data_in[{col}]_Xbank{bank}_Xdata_in".format(bank=bank, col=col))
            else:
                self.probe_labels.add("Xsram.Xbank{}.data_in[{}]".format(bank, col))

        # internal control buffer
        labels = ["bank_sel_cbar", "sel_clk_sense"]

        for i in range(len(labels)):
            self.probe_labels.add("Xsram.Xbank{}.Xcontrol_buffers.{}".format(bank, labels[i]))

        for i in range(len(self.sram.bank.control_buffers.clk_buf.buffer_stages)-2):
            if OPTS.use_pex:
                self.probe_labels.add("Xbank{}.Xcontrol_buffers.Xclk_buf.Xbuffer.out_{}".format(bank, i + 1))
            else:
                self.probe_labels.add("Xsram.Xbank{}.Xcontrol_buffers.Xclk_buf.Xbuffer.out_{}".format(bank, i+1))

        # decoder enable signals
        if not OPTS.baseline and OPTS.use_pex:
            self.probe_labels.add("Xsram.Xbank{bank}_dec_en_0_buf_Xbank{bank}_Xdecoder_logic_{rows}_Xen_0_{row}"
                                  .format(bank=bank, row=row, rows=self.sram.num_rows))
            self.probe_labels.add("Xsram.Xbank{bank}_dec_en_1_buf_Xbank{bank}_Xdecoder_logic_{rows}_Xen_1_{row}"
                                  .format(bank=bank, row=row, rows=self.sram.num_rows))

        # predecoder flop output
        if OPTS.use_pex:
            self.probe_labels.add("Xsram.Xbank{bank}_Xright_row_decoder_Xpre[0]_in[0]".format(bank=bank))
        if not OPTS.baseline and OPTS.use_pex:
            self.probe_labels.add("Xsram.Xbank{bank}_Xleft_row_decoder_Xpre[0]_in[0]".format(bank=bank))

        # predecoder flop clk
        if OPTS.use_pex:
            if OPTS.baseline:
                self.probe_labels.add("Xsram.Xbank{bank}_clk_buf_Xbank{bank}_Xright_row_decoder".format(bank=bank))
            else:
                self.probe_labels.add("clk_buf_Xbank{bank}_Xright_row_decoder".format(bank=bank))
        if not OPTS.baseline and OPTS.use_pex:
            self.probe_labels.add("clk_buf_Xbank{bank}_Xleft_row_decoder".format(bank=bank))

    def probe_dout_masks(self):
        bank = 0
        for col in range(self.sram.num_cols):
            if OPTS.baseline:
                self.dout_probes[col] = "D[{}]".format(col)
            elif not OPTS.use_pex:
                self.dout_probes[col] = "Xsram.Xbank{bank}.DATA[{col}]".format(bank=bank, col=col)
                self.mask_probes[col] = "Xsram.Xbank{bank}.mask_in_bar[{col}]".format(bank=bank, col=col)
            else:
                self.dout_probes[col] = "bus[{col}]_Xbank{bank}_Xdata_in_XXdff{col}".format(
                    bank=bank, col=col)
                self.mask_probes[col] = "mask_bar[{col}]_Xbank{bank}_Xwrite_driver_array" \
                                        "_Xdriver_{col}".format(bank=bank, col=col)

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

        if OPTS.use_pex:
            col = self.sram.num_cols - 1
            wl_label = "Xsram.Xbank{bank}.wl[{row}]_Xbank{bank}" \
                       "_Xbitcell_array_Xbit_r{row}_c{col}".format(bank=bank_index, row=row, col=col)
        else:
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
                bus_probes = [self.bitline_probes, self.decoder_probes, self.dout_probes, self.mask_probes]
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

        # AND/NOR/cout
        if not OPTS.baseline:
            for col in range(self.sram.num_cols):
                self.saved_nodes.add("and[{}]".format(col))
                self.saved_nodes.add("nor[{}]".format(col))
            if OPTS.serial:
                for col in range(self.sram.num_cols):
                    self.saved_nodes.add("c_val[{}]".format(col))
            else:
                for word in range(self.sram.alu_num_words):
                    self.saved_nodes.add("cout[{}]".format(word))

    def extract_from_pex(self, label, pex_file=None):

        prefix = "Xsram."
        if pex_file is None:
            if OPTS.top_level_pex:
                pex_file = self.pex_file
            else:
                pex_file = os.path.join(OPTS.openram_temp, self.sram.bank.name+"_pex.sp")
                prefix = "Xsram.Xbank0."
                label = label.replace("Xsram.Xbank0_", "")
                label = label.replace("_Xbank0", "")

        match = None
        try:
            label_sub = label.replace(prefix, "").replace(".", "_")\
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
        if OPTS.top_level_pex:
            return 'Xsram.' + match.decode().strip()
        else:
            return 'Xsram.Xbank0.' + match.decode().strip()
