import os

from characterizer.stimuli import stimuli
from globals import OPTS


class SpiceDut(stimuli):
    """
    Instantiates the sram
    External peripheral spice should also be instantiated here
    """
    words_per_row = 1

    def instantiate_sram(self, sram):
        super().instantiate_sram(sram)
        self.gen_constant("sense_amp_ref", OPTS.sense_amp_vref)

    @staticmethod
    def get_sram_pin_replacements(sram):
        replacements = stimuli.get_sram_pin_replacements(sram)
        replacements.extend([("ADDR_1[", "A_1["), ("dec_en_1", "en_1")])
        return replacements

    def write_include(self, circuit):
        """Include exported spice from cadence"""
        super().write_include(circuit)
        self.replace_pex_subcells()

    @staticmethod
    def replace_pex_subcells():
        if OPTS.use_pex and not OPTS.top_level_pex:
            pex_file = OPTS.pex_spice
            original_netlist = OPTS.spice_file
            module_names = [x.name for x in OPTS.pex_submodules]
            module_name = ""
            in_subcell = False
            with open(original_netlist, 'r') as original, open(pex_file, 'w') as pex:
                for line in original:
                    if line.startswith('.SUBCKT'):
                        module_name = line.split()[1]
                        if module_name in module_names:
                            in_subcell = True
                        else:
                            pex.write(line)
                    elif line.startswith('.ENDS'):
                        if in_subcell:
                            in_subcell = False
                            pex.write('.include {}\n'.format(
                                os.path.join(OPTS.openram_temp, module_name + '_pex.sp')))
                        else:
                            pex.write(line)
                    elif not in_subcell:
                        pex.write(line)
                pex.flush()
