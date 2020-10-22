import tech
from base import utils
from characterizer.sram_probe import SramProbe
from globals import OPTS


class CamProbe(SramProbe):

    def __init__(self, sram, pex_file=None):
        super(CamProbe, self).__init__(sram, pex_file)
        self.q_pin = utils.get_libcell_pins(["Q"], "cam_cell_6t", tech.GDS["unit"],
                                            tech.layer["boundary"]).get("q")[0]
        self.qbar_pin = utils.get_libcell_pins(["QBAR"], "cam_cell_6t",
                                               tech.GDS["unit"], tech.layer["boundary"]).get("qbar")[0]
        self.matchline_probes = {}
        self.write_wordline_probes = {}

    def get_bitcell_label(self, bank_index, row, col, pin_name):
        (cam_block, col_num) = self.get_col_location(col)
        return "Xsram.Xbank{}.Xcam_block{}.Xbitcell_array.Xbit_r{}_c{}.{}".format(bank_index, cam_block, row,
                                                                                  col_num, pin_name)

    def get_bitcell_pin(self, pin, bank_inst, row, col):
        (cam_block, col_num) = self.get_col_location(col)
        block_inst = bank_inst.mod.block_insts[cam_block]
        return utils.get_pin_rect(pin, [bank_inst, block_inst, block_inst.mod.bitcell_array_inst,
                                        block_inst.mod.bitcell_array_inst.mod.cell_inst[row, col_num]])

    def get_bitline_label(self, bank_index, pin_name, col):
        (cam_block, col_num) = self.get_col_location(col)
        return "Xsram.Xbank{}.Xcam_block{}.Xbitcell_array.{}[{}]".format(bank_index, cam_block, pin_name, col_num)

    def get_bitline_pin(self, pin_name, bank_inst, col):
        (cam_block, col_num) = self.get_col_location(col)
        block_inst = bank_inst.mod.block_insts[cam_block]

        pin = block_inst.mod.bitcell_array_inst.get_pin("{}[{}]".format(pin_name, col_num))
        ll, ur = utils.get_pin_rect(pin, [bank_inst, block_inst])
        return pin, ll, ur

    def get_wordline_label(self, bank_index, row, col_index):
        return "Xsram.Xbank{}.Xcam_block{}.Xbitcell_array.wl[{}]".format(bank_index, col_index, row)

    def get_wordline_pin(self, bank_inst, row, col_index):
        block_inst = bank_inst.mod.block_insts[col_index]
        pin = block_inst.mod.bitcell_array_inst.get_pin("wl[{}]".format(row))
        ll, ur = utils.get_pin_rect(pin, [bank_inst, block_inst])
        return pin, ll, ur

    def probe_sense_amps(self, bank_index, bank_inst, pin_name):
        pass

    def probe_word_driver_clk(self, bank_index, bank_inst):
        pass

    def probe_sense_amp(self, address):
        address = self.address_to_vector(address)
        bank_index, bank_inst, row, col_index = self.decode_address(address)
        if OPTS.use_pex:
            pass
        else:
            self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.gated_s_en".format(bank_index, col_index, row))
            for i in range(self.sram.word_size):
                self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.data_out[{}]".format(bank_index, col_index, i))

    def probe_matchline(self, address):
        address_int = address
        address = self.address_to_vector(address)
        bank_index, bank_inst, row, col_index = self.decode_address(address)
        if OPTS.use_pex:
            block_inst = bank_inst.mod.block_insts[col_index]
            label_key = "ml_b{}_c{}_r{}".format(bank_index, col_index, row)
            pin = block_inst.mod.tag_flop_array_inst.get_pin("din[{}]".format(row))
            ll, ur = utils.get_pin_rect(pin, [bank_inst, block_inst])
            pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
            self.sram.add_label(label_key, pin.layer, pin_loc)
            self.matchline_probes[address_int] = label_key
            self.probe_labels.add(label_key)
        else:

            label_key = "Xsram.Xbank{}.Xcam_block{}.ml[{}]".format(bank_index, col_index, row)
            self.probe_labels.add(label_key)
            self.matchline_probes[address_int] = label_key

    def probe_write_wordlines(self, address):
        """add labels to write wordlines
                labels should be unique by bank and row
                """

        address = self.address_to_vector(address)
        bank_index, bank_inst, row, col_index = self.decode_address(address)

        label_key = "wwl_b{}_r{}".format(bank_index, row)

        if label_key in self.wordline_probes:
            return

        if OPTS.use_pex:
            block_inst = bank_inst.mod.block_insts[col_index]
            pin = block_inst.mod.bitcell_array_inst.get_pin("wwl[{}]".format(row))
            ll, ur = utils.get_pin_rect(pin, [bank_inst, block_inst])

            pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
            self.sram.add_label(label_key, pin.layer, pin_loc)
            self.write_wordline_probes[label_key] = label_key
        else:
            self.write_wordline_probes[label_key] = \
                "Xsram.Xbank{}.Xcam_block{}.Xbitcell_array.wwl[{}]".format(bank_index, col_index, row)
        self.probe_labels.add(self.write_wordline_probes[label_key])

    def get_matchline_probe(self, address, pex_file=None):
        if OPTS.use_pex:
            return self.extract_from_pex(self.matchline_probes[address], pex_file)
        else:
            return self.matchline_probes[address]

    def probe_tagbits(self, address):
        address = self.address_to_vector(address)
        bank_index, bank_inst, row, col_index = self.decode_address(address)
        if OPTS.use_pex:
            pass
        else:
            self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.tag[{}]".format(bank_index, col_index, row))

    def add_misc_bank_probes(self, bank_inst, bank_index):
        pass

    def add_misc_addr_probes(self, addresses):
        address = self.address_to_vector(addresses[0])
        bank_index, bank_inst, row, col_index = self.decode_address(address)
        block_inst = bank_inst.mod.block_insts[col_index]

        self.probe_pin(bank_inst.get_pin("clk_buf"), "clk_buf", [])

        self.add_probe_at_pin("gated_clk_buf_b{}".format(bank_index),
                              block_inst.mod.bank_gate_inst.get_pin("gated_clk".format(row)), bank_inst, block_inst)
        self.add_probe_at_pin("gated_clk_bar_b{}".format(bank_index),
                              block_inst.mod.bank_gate_inst.get_pin("gated_clk_bar".format(row)), bank_inst, block_inst)
        self.add_probe_at_pin("gated_s_en_b{}".format(bank_index),
                              block_inst.mod.bank_gate_inst.get_pin("gated_s_en".format(row)), bank_inst, block_inst)
        self.add_probe_at_pin("gated_w_en_b{}".format(bank_index),
                              block_inst.mod.bank_gate_inst.get_pin("gated_w_en".format(row)), bank_inst, block_inst)

    def add_probe_at_pin(self, label, pin, bank_inst, block_inst):
        ll, ur = utils.get_pin_rect(pin, [bank_inst, block_inst])
        pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
        self.sram.add_label(label, pin.layer, pin_loc)
        self.probe_labels.add(label)

    def add_misc_probes(self, bank_inst):
        self.probe_labels.add("Xsram.Xbank{}.sel_all_banks".format(0))
        self.probe_labels.add("Xsram.Xbank{}.Xrow_decoder.Xpre[0].flop_in[0]".format(0))
        self.probe_labels.add("Xsram.Xbank{}.Xrow_decoder.Xpre[0].in[0]".format(0))
        self.probe_labels.add("Xsram.Xbank{}.Xrow_decoder.Xpre[0].inbar[0]".format(0))
        self.probe_labels.add("Xsram.Xbank{}.Xrow_decoder.out[0]".format(0))
        self.probe_labels.add("Xsram.Xbank{}.Xrow_decoder.out[1]".format(0))
        self.probe_labels.add("Xsram.Xbank{}.Xrow_decoder.out[2]".format(0))
        self.probe_labels.add("Xsram.Xbank{}.Xrow_decoder.out[3]".format(0))

        for block in [0]:
            self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.Xbank_gate.sel".format(0, block))
            self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.gated_s_en".format(0, block))
            self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.gated_w_en".format(0, block))
            self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.gated_search_en".format(0, block))
            self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.gated_mw_en".format(0, block))
            self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.gated_sel_all_rows".format(0, block))
            self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.gated_latch_tags".format(0, block))
            self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.gated_clk_buf".format(0, block))
            self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.gated_clk_bar".format(0, block))
            for col in range(self.sram.word_size):
                self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.mask_in[{}]".format(0, block, col))
                self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.data_in[{}]".format(0, block, col))
                self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.bl[{}]".format(0, block, col))
                self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.br[{}]".format(0, block, col))
            for row in range(self.sram.num_rows):
                self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.wl_in[{}]".format(0, block, row))
                self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.dec_out[{}]".format(0, block, row))
                self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.wl[{}]".format(0, block, row))
                self.probe_labels.add("Xsram.Xbank{}.Xcam_block{}.ml[{}]".format(0, block, row))

    def get_col_location(self, col):
        cam_block = col % self.sram.words_per_row
        col_num = int(col / self.sram.words_per_row)
        return cam_block, col_num
