from collections import defaultdict

import re

import debug

# TODO just a [terrible] hack for now. Very specific to reram, doesn't work for multiple banks

bank_pattern = re.compile(r"Xbank([0-9]+)")
row_col_pattern = re.compile(r"_r([0-9]+)_c([0-9]+)")
child_mod_pattern = re.compile("Xmod_([0-9]+)")
parenthesis_pattern = re.compile(r"\[([0-9]+)\]")
wordline_en_pattern = re.compile(r"bank\S+wordline_driver\S+/en")


def get_adjacent_source_drain(net, device):
    terminals = MagicLabelExtractor.devices_to_nets[device][0]
    if terminals.index(net) == 0:
        return terminals[2]
    return terminals[0]


def get_reram_device(label):
    row, col = row_col_pattern.findall(label)[0]
    bank = get_bank(label)
    net_to_devices = MagicLabelExtractor.net_to_devices

    bl = get_bitline_probe(bank, col, "bl")
    br = get_bitline_probe(bank, col, "br")
    wordline = get_wordline_probe(bank, row, "wl")
    if not bl or not wordline or not br:
        return None
    access_tx = set(net_to_devices[br]).intersection(net_to_devices[wordline])
    if not access_tx:
        debug.warning("Access device not found for %s", label)
    access_tx = next(iter(access_tx))

    reram_net = get_adjacent_source_drain(br, access_tx[0])

    reram_device = [x for x in net_to_devices[reram_net]
                    if x[1] == "sky130_fd_pr__reram_reram_cell"][0]
    return reram_device


def extract_state_probe(label):
    # suffix = row_col_pattern.split(label)[-1]
    return get_reram_device(label)[0] + ".state_out"


def get_bank(label):
    # return bank_pattern.findall(label)[0][0]
    return 0


def search_pattern(pattern, str_=None):
    if str_ is None:
        str_ = MagicLabelExtractor.net_names_str
    match = pattern.search(str_)
    if match:
        return match.group()
    return None


def get_bank_probe(net_name, index=None, bank=0):
    net_name = net_name.replace("[", "\[").replace("]", "\]")
    if index is None:
        pattern = re.compile(rf"bank\S+/{net_name}")
    else:
        pattern = re.compile(rf"bank\S+/\S+/{net_name}\[{index}\]")
    return search_pattern(pattern)


def get_bitline_probe(bank, col, bl_name="bl"):
    return get_bank_probe(bl_name, col)


def get_wordline_probe(bank, row, wl__name="wl"):
    return get_bank_probe(wl__name, row, bank)


def get_driver_index(label):
    return child_mod_pattern.findall(label)[0]


def get_write_driver_net(label):
    suffix = label.split(".")[-1]
    driver_index = get_driver_index(label)
    net = suffix[:-2]

    data_net = get_bank_probe(net, driver_index)
    for inst_name, _ in MagicLabelExtractor.net_to_devices[data_net]:
        terminals, _ = MagicLabelExtractor.devices_to_nets[inst_name]
        for terminal in terminals:
            if terminal.endswith(suffix):
                return terminal
    return None


def get_sense_amp_net(label, net_name, bank=0):
    net_to_devices = MagicLabelExtractor.net_to_devices
    if net_name == "vdata":
        bit = get_driver_index(label)
        words_per_row = getattr(MagicLabelExtractor.parent_mod, "words_per_row", 1)
        bl_name = "bl" if words_per_row == 1 else "bl_out"
        bitline_net = get_bitline_probe(bank, bit, bl_name)
        devices = set(net_to_devices["vclamp"]).intersection(net_to_devices[bitline_net])
        return get_adjacent_source_drain(bitline_net, next(iter(devices))[0])
    else:
        bit = parenthesis_pattern.findall(label)[0]
        pattern = re.compile(fr"bank\S+sense\S+/dout\[{bit}\]")
        return search_pattern(pattern)


def get_enable_net(label, net_name):
    if net_name == "sample_en_bar":
        internal_net = "sampleb"
    elif net_name.endswith("_bar"):
        internal_net = "en_bar"
    else:
        internal_net = "en"
    if net_name == "wordline_en":
        inst_name = "wordline_driver"
    elif net_name == "write_en":
        inst_name = "write_driver"
    elif net_name in ["sense_en", "sample_en_bar"]:
        inst_name = "sense_amp"
    else:
        inst_name = "tri_gate"

    pattern = re.compile(fr"bank\S+{inst_name}\S+/{internal_net}")
    return search_pattern(pattern)


def get_flop_data_net(label):
    suffix = label.split(".")[-1]
    driver_index = parenthesis_pattern.findall(suffix)[0]
    net = suffix.split("[")[0].replace("_in", "")
    return get_bank_probe(net, driver_index)


class MagicLabelExtractor:
    pex_file = None
    net_names_str = ""
    net_names = set()
    net_to_devices = {}
    devices_to_nets = {}
    pins = []
    parent_mod = None

    @staticmethod
    def load_pex_file(pex_file, parent_mod):

        debug.info(1, "Loading magic pex file %s", pex_file)
        MagicLabelExtractor.pex_file = pex_file
        MagicLabelExtractor.net_names = net_names = set()
        MagicLabelExtractor.net_to_devices = net_to_devices = defaultdict(list)
        MagicLabelExtractor.devices_to_nets = devices_to_nets = {}
        MagicLabelExtractor.parent_mod = parent_mod

        if parent_mod and hasattr(parent_mod, "pins"):
            MagicLabelExtractor.pins = parent_mod.pins
        else:
            MagicLabelExtractor.pins = []

        with open(pex_file, "r") as f:
            for line in f.readlines():
                if line[0] == "X" or line[0] == "m":
                    line_split = line.split(" ")
                    # remove properties
                    line_split = [x for x in line_split if "=" not in x]
                    # first should be instance name, last should be device name
                    instance_name = line_split[0]
                    terminals = line_split[1:-1]
                    device_type = line_split[-1]

                    devices_to_nets[instance_name] = (terminals, device_type)

                    net_names.update(terminals)
                    for net in terminals:
                        net_to_devices[net].append((instance_name, device_type))
                elif len(net_names) > 0:
                    break
        MagicLabelExtractor.net_names_str = " ".join(net_names)

    @staticmethod
    def extract(label, magic_file, parent_mod):
        if not magic_file == MagicLabelExtractor.pex_file:
            MagicLabelExtractor.load_pex_file(magic_file, parent_mod)

        suffix = label.split(".")[-1]
        num_stems = len(label.split("."))

        match = None

        if label in MagicLabelExtractor.pins:
            return label, label
        if suffix == "state_out":
            match = extract_state_probe(label)
        elif num_stems <= 2:
            match = get_bank_probe(suffix)

        if match is None:

            if "[" in suffix:
                net_name, index = suffix.split("[")
            else:
                net_name = suffix

            if net_name in ["bank_sel_buf", "read_buf"]:  # ignore
                match = "gnd"
            elif net_name in ["write_en", "wordline_en", "sense_en",
                              "tri_en", "tri_en_bar", "sample_en_bar"]:
                match = get_enable_net(label, net_name)
            elif suffix in ["bl_p", "bl_n", "br_p", "br_n"]:
                match = get_write_driver_net(label)
            elif net_name in ["sense_out", "vdata"]:
                match = get_sense_amp_net(label, net_name)
            else:
                if "[" in suffix:
                    net_name, index = suffix.split("[")
                    if net_name in ["data_in", "mask_in"]:
                        match = get_flop_data_net(label)
                    elif net_name in ["dec_out", "decoder_clk"]:
                        match = get_bank_probe(suffix)

        assert match is not None, "Label not found"

        return match, label
