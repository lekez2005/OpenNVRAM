import re

from characterizer.net_probes.sram_probe import SramProbe
from globals import OPTS

X_MOD_TEMPLATE = re.compile(r"(\S+)(Xmod_)\{bit\}(\S+)", re.IGNORECASE)


class PushRulesProbe(SramProbe):

    @staticmethod
    def filter_internal_nets(child_mod, candidate_nets):
        netlist = child_mod.get_spice_parser().get_module(child_mod.name).contents
        netlist = "\n".join(netlist)
        if netlist.startswith("xchild_mod"):
            child_mod = child_mod.child_mod
        return SramProbe.filter_internal_nets(child_mod, candidate_nets=candidate_nets)

    def format_full_internal_net(self, template, bit):
        for array_name in ["sense_amp_array", "tri_gate_array", "Xmask_in", "Xdata_in"]:
            if array_name in template:
                if bit % 2 == 1:
                    template = template.replace("<0>", "<1>")
                mod_bit = int(bit / 2)
                if OPTS.use_pex:
                    # replace twice
                    template = X_MOD_TEMPLATE.sub(rf"\g<1>\g<2>{mod_bit}\g<3>", template)
                    template = X_MOD_TEMPLATE.sub(rf"\g<1>\g<2>{mod_bit}\g<3>", template)
                else:
                    template = template.replace("Xmod_{bit}", f"Xmod_{mod_bit}")

        return template.format(bit=bit)
