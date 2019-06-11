import tech
from base import utils
from characterizer.sram_probe import SramProbe
from globals import OPTS


class SfCamProbe(SramProbe):

    def __init__(self, sram, pex_file=None):
        super().__init__(sram, pex_file)
        self.q_pin = utils.get_libcell_pins(["Q"], "cam_cell_6t", tech.GDS["unit"], tech.layer["boundary"]).get("Q")[0]
        self.qbar_pin = utils.get_libcell_pins(["QBAR"], "cam_cell_6t",
                                               tech.GDS["unit"], tech.layer["boundary"]).get("QBAR")[0]
        self.state_probes = {}
        self.matchline_probes = {}
        self.decoder_probes = {}

    def probe_address(self, address, pin_name="mz1"):
        address = self.address_to_vector(address)
        address_int = self.address_to_int(address)

        bank_index, bank_inst, row, col_index = self.decode_address(address)

        decoder_label = "Xsram.Xbank{}.dec_out[{}]".format(bank_index, row)
        self.decoder_probes[address_int] = decoder_label
        self.probe_labels.add(decoder_label)

        wl_label = "Xsram.Xbank{}.wl[{}]".format(bank_index, row)
        self.wordline_probes[address_int] = wl_label
        self.probe_labels.add(wl_label)

        self.probe_labels.add("Xsram.Xbank{}.search_out[{}]".format(bank_index, row))

        pin_labels = [""] * self.sram.word_size
        for i in range(self.sram.num_cols):
            col = i * self.sram.words_per_row + self.address_to_int(col_index)
            pin_labels[i] = "Xsram.Xbank{}.Xbitcell_array.Xbit_r{}_c{}.{}".format(bank_index, row, col, pin_name)

        pin_labels.reverse()
        self.probe_labels.update(pin_labels)
        self.state_probes[address_int] = pin_labels

    def probe_matchline(self, address):
        address_int = address
        address = self.address_to_vector(address)
        bank_index, bank_inst, row, col_index = self.decode_address(address)
        if OPTS.use_pex:
            label_key = "ml_b{}_r{}".format(bank_index, row)
            pin = bank_inst.mod.tag_flop_array_inst.get_pin("din[{}]".format(row))
            ll, ur = utils.get_pin_rect(pin, [bank_inst])
            pin_loc = [0.5 * (ll[0] + ur[0]), 0.5 * (ll[1] + ur[1])]
            self.sram.add_label(label_key, pin.layer, pin_loc)
            self.matchline_probes[address_int] = label_key
            self.probe_labels.add(label_key)
        else:

            label_key = "Xsram.Xbank{}.ml[{}]".format(bank_index, row)
            self.probe_labels.add(label_key)
            self.matchline_probes[address_int] = label_key
