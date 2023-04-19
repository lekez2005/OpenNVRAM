from characterizer.net_probes.sram_probe import SramProbe
from globals import OPTS


class BlProbe(SramProbe):
    """
    Adds probe labels to the sram such that the label names are partially retained post extraction
    The actual post extraction label is obtained using regex
    """

    def __init__(self, sram, pex_file=None):
        super().__init__(sram, pex_file)
        self.external_probes = ["mask", "data_in", "cout"]
        if OPTS.serial:
            self.external_probes.append("c_val")
        else:
            self.external_probes.append("cin")
        self.and_probes = self.voltage_probes["and"] = {}
        self.nor_probes = self.voltage_probes["nor"] = {}

    def probe_bank(self, bank):
        super().probe_bank(bank)
        self.probe_dout_masks()
        if not OPTS.baseline:
            self.probe_alu()

    def probe_bank_currents(self, bank):
        has_mask_in = self.sram.bank.has_mask_in
        if not OPTS.baseline:
            self.sram.bank.has_mask_in = False
        super().probe_bank_currents(bank)
        self.sram.bank.has_mask_in = has_mask_in

    @staticmethod
    def replace_alu_template(sample_net):
        net_template = sample_net.replace("mcc0", "mcc{col}").replace("[0]", "[{col}]")
        return net_template.replace("mcc1", "mcc{col}").replace("[1]", "[{col}]")

    def probe_dout_masks(self):
        self.voltage_probes["bank_mask_bar"] = {}
        for col in range(self.sram.num_cols):
            self.and_probes[col] = self.probe_net_at_inst(f"and[{col}]", self.sram.alu_inst)
            self.nor_probes[col] = self.probe_net_at_inst(f"nor[{col}]", self.sram.alu_inst)

            if OPTS.baseline:
                self.dout_probes[col] = f"D[{col}]"
            else:
                dout_net = self.probe_net_at_inst(f"bus[{col}]", self.sram.alu_inst)
                self.dout_probes[col] = dout_net
                if not OPTS.baseline:
                    mask_net = self.probe_net_at_inst(f"mask_bar[{col}]", self.sram.alu_inst)
                    self.voltage_probes["bank_mask_bar"][col] = mask_net

        self.voltage_probes[self.sram.bank.sense_amp_array_inst.name][0]["and"] = self.and_probes
        self.voltage_probes[self.sram.bank.sense_amp_array_inst.name][0]["nor"] = self.nor_probes

    def get_sense_amp_internal_nets(self):
        if OPTS.sense_amp_type == OPTS.MIRROR_SENSE_AMP:
            return ["bl", "br"]
        return super().get_sense_amp_internal_nets()

    def sense_amp_current_probes(self, bank, bits):
        probes = self.bitline_current_probes(bank, bits, modules=["sense_amp_array"],
                                             nets=["and", "nor"],
                                             suffix="")
        self.update_current_probes(probes, "sense_amp_array", bank)

    def tri_state_current_probes(self, bank, bits):
        pass

    def probe_control_flops(self, bank):
        super().probe_control_flops(bank)
        self.probe_labels.add(self.probe_net_at_inst("Xbank0.dec_en_1",
                                                     self.sram.bank.decoder_logic_inst))

    def probe_alu_internal_nets(self):
        # internal nets
        internal_nets = ["and", "nand"]
        for net in internal_nets:
            self.voltage_probes["alu"][net] = {}
            sample_net = self.probe_net_at_inst(f"Xalu.Xmcc0.{net}", self.sram.alu_inst)
            net_template = sample_net.replace("mcc0", "mcc{col}")
            for col in OPTS.probe_cols:
                self.voltage_probes["alu"][net][col] = net_template.format(col=col)

    def probe_alu(self):
        self.probe_labels.add(self.probe_net_at_inst("decoder_clk", self.sram.left_decoder_inst))
        self.probe_labels.add(self.probe_net_at_inst("decoder_clk", self.sram.right_decoder_inst))
        if OPTS.baseline:
            return

        self.probe_labels.add("Xsram.Xalu.sr_clk_buf")
        self.voltage_probes["alu"] = {}
        self.probe_alu_internal_nets()

        probe_nets = []
        if OPTS.serial:
            probe_nets.extend(["cin[{col}]", "c_val[{col}]", "cout[{col}]"])
        else:
            probe_nets.extend(["cin[{col}]", "Xalu.shift_out[{col}]", "Xalu.cout_int[{col}]",
                               "Xalu.coutb_int[{col}]", "cout[{col}]"])
            # handle nested net "Xalu.Xmcc0.XI8.net1"
        for probe_net in probe_nets:
            net_key = probe_net.split(".", )[-1].replace("[{col}]", "")

            if net_key in self.external_probes:
                self.voltage_probes[net_key] = {}
            else:
                self.voltage_probes["alu"][net_key] = {}

            if net_key == "c_val":
                probe_cols = range(self.sram.num_cols)
            elif net_key in ["cin", "cout"]:
                probe_cols = range(self.sram.alu_num_words)
            else:
                probe_cols = OPTS.probe_cols

            for col in probe_cols:
                max_bit = OPTS.alu_word_size - 1
                if net_key == "coutb_int" and (col % 2 == 1 or col % OPTS.alu_word_size == max_bit):
                    continue
                if net_key == "cout_int" and (col % 2 == 0 or (col + 1) % OPTS.alu_word_size == 0):
                    continue
                if net_key not in self.external_probes:
                    probe_val = self.probe_net_at_inst(probe_net.format(col=col),
                                                       self.sram.alu_inst)
                    self.voltage_probes["alu"][net_key][col] = probe_val
                else:
                    self.voltage_probes[net_key][col] = probe_net.format(col=col)

    @staticmethod
    def get_decoder_out_nets():
        if OPTS.baseline:
            return ["dec_out[0]"]
        else:
            nets = ["Xbank{bank}.dec_out[0]"]
            if OPTS.verbose_save:
                nets.extend(["dec_in_0[0]", "dec_in_1[0]"])
            return nets

    def add_decoder_inputs(self, address_int, row, bank_index):
        net_probes = []
        for net in self.get_decoder_out_nets():
            net = net.format(bank=bank_index)
            sample_net = self.probe_net_at_inst(net, self.sram.bank_inst)
            net_template = sample_net.replace("[0]", "[{row}]")
            net_template = net_template.replace("xen_bar_0", "xen_bar_{row}")
            net_template = net_template.replace("xin_0_0", "xin_0_{row}")
            net_template = net_template.replace("xin_1_0", "xin_1_{row}")
            net_probes.append(net_template.format(row=row))
        self.decoder_probes[address_int] = net_probes[0]
        self.probe_labels.update(net_probes)

    def extract_probes(self):
        self.probe_labels.update(self.and_probes.values())
        self.probe_labels.update(self.nor_probes.values())
        for key in self.external_probes:
            if key in self.voltage_probes:
                self.saved_nodes.update(self.voltage_probes[key].values())

        for key in ["alu", "bank_mask_bar"]:
            if key not in self.voltage_probes:
                continue
            for val in self.voltage_probes[key].values():
                if isinstance(val, dict):
                    self.probe_labels.update(val.values())
                else:
                    self.probe_labels.add(val)
        super().extract_probes()

    def extract_from_pex(self, label, pex_file=None):
        net = super().extract_from_pex(label, pex_file)
        if not OPTS.top_level_pex:
            net = net.replace('Xsram.', 'Xsram,Xbank0.')
        return net
