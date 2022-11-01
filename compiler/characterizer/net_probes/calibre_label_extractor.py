import re
import debug

from base.spice_parser import SpiceParser


def load_device(line):
    first_letter = line[0].lower()
    if first_letter in ["x", "m", "d"]:
        line_split = line.split(" ")
        # remove properties
        line_split = [x for x in line_split if "=" not in x]
        # first should be instance name, last should be device name
        instance_name = line_split[0]
        terminals = line_split[1:-1]
        device_type = line_split[-1]
        return instance_name, terminals, device_type
    return None


class CalibreLabelExtractor:
    pex_file = None
    net_names_set = set()
    net_names_lower = []
    net_names_orig = []
    net_names_str = ""
    parent_mod = None

    @classmethod
    def load_pex_file(cls, pex_file, parent_mod):
        debug.info(1, "Loading calibre pex file %s", pex_file)
        cls.pex_file = pex_file
        cls.net_names = net_names = set()
        cls.parent_mod = parent_mod

        with open(pex_file, "r") as f:
            parser = SpiceParser(f, lower_case=False)

            for line in parser.mods[0].contents:
                device = load_device(line)
                if device is not None:
                    instance_name, terminals, device_type = device
                    net_names.update(terminals)
        cls.net_names_orig = [x for x in net_names]
        cls.net_names_lower = [x.lower() for x in net_names]
        cls.net_names = set(cls.net_names_lower)
        cls.net_names_str = " ".join(cls.net_names)

    @classmethod
    def extract(cls, pattern, pex_file, parent_mod):
        if not pex_file == CalibreLabelExtractor.pex_file:
            CalibreLabelExtractor.load_pex_file(pex_file, parent_mod)

        # if pattern in CalibreLabelExtractor.net_names:
        #     match = pattern
        match = re.search(pattern, cls.net_names_str)
        if match:
            match = match.group()
            match = cls.net_names_orig[cls.net_names_lower.index(match)]
        return match, pattern
