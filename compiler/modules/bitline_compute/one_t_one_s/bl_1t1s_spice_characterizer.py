import itertools
import math
import re
from collections import defaultdict

from characterizer import stimuli
from globals import OPTS
from modules.bitline_compute.bitline_spice_characterizer import BitlineSpiceCharacterizer, alu_sum
from modules.bitline_compute.bl_probe import BlProbe
from modules.mram.mram_sim_steps_generator import WriteTrigMixin
from modules.mram.spice_dut import SpiceDut

row_col_pattern = re.compile(r"bit_(r[0-9]+_c[0-9]+)", re.IGNORECASE)


class Bl1t1sSpiceDut(SpiceDut):
    pex_map = defaultdict(list)

    def instantiate_sram(self, sram):
        super().instantiate_sram(sram)
        # add cap to A_1 to preserve node
        self.sf.write(f"CA_1[0] A_1[0] 0 0.1f\n")

    @staticmethod
    def get_sram_pin_replacements(sram):
        replacements = stimuli.get_sram_pin_replacements(sram)
        replacements.extend([("ADDR_1[", "A_1["), ("dec_en_1", "en_1"), ("sense_amp_ref", "vref")])
        return replacements

    @staticmethod
    def do_cell_replacement(definition_split, match_groups, dest_f, format_tx):

        drain, gate, source, body = definition_split[1:5]

        if "wwl" in gate.lower():
            dest_f.write(format_tx())
        row_col = row_col_pattern.findall(definition_split[0])[0]

        cell_pins = Bl1t1sSpiceDut.pex_map[row_col]
        cell_pins.extend([drain, gate, source])

        # total_fingers = 4 + 2  # 2 2-finger tx + 2 1-finger tx
        # total terminals = 6 * 3

        if len(cell_pins) < 18:
            return

        def locate_net(prefix):
            return [x for x in cell_pins if prefix in x][0]

        rwl = locate_net("rwl")
        bl_p, br_p, bl_g, br_g = map(locate_net, ["bl_p", "br_p", "bl_g", "br_g"])
        bl, br, blb, brb = map(locate_net, ["bl[", "br[", "blb[", "brb["])

        name_template = OPTS.bitcell_name_template

        sotfet_nets = [(bl, bl_p, bl, rwl, body), [br, br_p, br, rwl, body]]
        resistance_nets = [(bl, bl_g), (br, br_g)]  # to include parasitics from gate

        for i in range(2):
            sotfet_cell_name = "{}_X{}".format(name_template.format(**match_groups), i)
            dest_f.write("{} {} {} {} {} {} {}\n".format(sotfet_cell_name, *sotfet_nets[i], "sotfet"))
            r1_net, r2_net = resistance_nets[i]
            dest_f.write(f"rshort_{row_col}_{i} {r1_net} {r2_net} {OPTS.pex_short_resistance}\n")

        del Bl1t1sSpiceDut.pex_map[row_col]


class Bl1t1sProbe(BlProbe):
    def __init__(self, sram, pex_file=None):
        super().__init__(sram, pex_file)
        self.wwl_probes = self.voltage_probes["wwl"] = {}

    def extract_from_pex(self, label, pex_file=None):
        for suffix in ["I8.vg_nfet", "I8.D", "I8.S"]:
            if label.endswith(suffix):
                self.saved_nodes.add(label)
                return label
        return super().extract_from_pex(label, pex_file)

    def probe_control_flops(self, bank):
        super().probe_control_flops(bank)
        self.sense_amp_current_probes(bank, OPTS.probe_bits)

    def sense_amp_current_probes(self, bank, bits):
        probes = self.bitline_current_probes(bank, bits, modules=["sense_amp_array"],
                                             nets=["bl"], suffix="")
        self.update_current_probes(probes, "sense_amp_array", bank)

    def probe_address(self, address, pin_name="q"):
        super().probe_address(address, pin_name)

        address = self.address_to_vector(address)
        address_int = self.address_to_int(address)
        bank_index, _, row, _ = self.decode_address(address)

        # add wwl probe
        col = self.sram.num_cols - 1
        self.wwl_probes[address_int] = self.get_wwl_label(bank_index, row, col)
        self.probe_labels.add(self.wwl_probes[address_int])
        if address_int % 2 == 0:
            self.probe_address(address_int + 1)

    def update_bitcell_labels(self, pin_labels):
        if not OPTS.use_pex:
            self.probe_labels.update(pin_labels)

    def extract_state_probes(self, existing_mappings):
        if OPTS.use_pex:
            dot_index = -9

            def replace_underscore(net):
                return net[:dot_index] + "_" + net[dot_index + 1:]

            for address in list(self.state_probes.keys()):
                self.state_probes[address] = list(map(replace_underscore, self.state_probes[address]))
                self.saved_nodes.update(self.state_probes[address])
        else:
            for key in self.state_probes:
                self.extract_nested_probe(key, self.state_probes, existing_mappings)

    def get_control_buffers_probe_bits(self, destination_inst, bank, net=None):
        name = destination_inst.name
        if name in ["wwl_driver", "rwl_driver"]:
            return [self.sram.bank.num_rows - 1]
        else:
            return super().get_control_buffers_probe_bits(destination_inst, bank)

    def probe_bitcell_currents(self, address):
        assert address % 2 == 0, "Only even addresses should be probed directly"
        super().probe_bitcell_currents(address)
        super().probe_bitcell_currents(address + 1)

    def wordline_driver_currents(self, address):
        pass

    def get_bank_bitcell_current_probes(self, bank, bits, row, col_index):
        if OPTS.use_pex:
            template = "Xsram.Xbank{}_Xbitcell_array_Xbit_r{}_c{}_"
        else:
            template = "Xsram.Xbank{}.Xbitcell_array.Xbit_r{}_c{}."
        template += f"X{col_index}.VIY"
        results = []
        for bit in bits:
            results.append((bit, template.format(bank, row, bit)))
        return results

    def get_bitcell_label(self, bank_index, row, col, pin_name):
        suffix = str(col % 2)
        col = int(col / 2)
        OPTS.bitcell_state_probe = f"X{suffix}.state"
        return super().get_bitcell_label(bank_index, row, col, OPTS.bitcell_state_probe)

    def get_wordline_nets(self):
        return ["wwl", "rwl"]

    def get_write_driver_internal_nets(self):
        return ["vdd", "data"]

    @staticmethod
    def get_bitline_names():
        return ["bl", "br", "blb", "brb"]

    def get_wordline_label(self, bank_index, row, col):
        return super().get_wordline_label(bank_index, row, col, wl_net="rwl")

    def get_wwl_label(self, bank_index, row, col):
        return super().get_wordline_label(bank_index, row, col, wl_net="wwl")

    def probe_internal_nets(self, bank_, sample_net, array_inst, internal_nets):
        if sample_net == "bl_out[0]":
            sample_net = "bl[0]"
        super().probe_internal_nets(bank_, sample_net, array_inst, internal_nets)


class Bl1t1sSpiceCharacterizer(WriteTrigMixin, BitlineSpiceCharacterizer):
    def __init__(self, sram, *args, **kwargs):
        super().__init__(sram, *args, **kwargs)
        self.has_write_measurements = False
        self.has_read_measurements = False
        self.force_select_nor = False
        self.num_writes = 0

    def create_dut(self):
        dut = Bl1t1sSpiceDut(self.sf, self.corner)
        dut.words_per_row = 1
        return dut

    def create_probe(self):
        self.probe = Bl1t1sProbe(self.sram, OPTS.pex_spice)

    def probe_delay_addresses(self):
        # TODO addresses to use?
        num_words = self.sram.num_words
        a_address = num_words - 2  # measure using topmost row
        b_address = 0
        c_address = int(num_words / 2)
        self.all_addresses = [a_address, b_address, c_address]
        self.probe_all_addresses(self.all_addresses, self.get_delay_probe_cols())
        self.probe.voltage_probes["control_buffers"][0]["wordline_en"] = \
            self.probe.voltage_probes["control_buffers"][0]["rwl_en"]

    def set_probe_cols_and_bits(self, probe_cols):
        probe_cols = [int(x / OPTS.words_per_row) * OPTS.words_per_row for x in probe_cols]
        OPTS.probe_cols = probe_cols
        OPTS.probe_bits = [x for x in OPTS.probe_cols]

    def setup_write_measurements(self, address_int):
        self.has_write_measurements = True
        super().setup_write_measurements(address_int)

    def wr(self, addr, data_v, mask_v):
        if self.num_writes == 0:
            super().wr(addr, self.invert_vec(data_v), [0 for _ in mask_v])
            self.log_event("Write", addr)

        super().wr(addr, data_v, mask_v)
        if addr % 2 == 1:
            assert False, "Odd addresses should not be directly written to"
        adjacent_address = addr + 1
        if self.has_write_measurements:
            self.setup_write_measurements(adjacent_address)
        super().wr(adjacent_address, self.invert_vec(data_v), mask_v)
        self.has_write_measurements = False

    def wb(self, addr, src, cond):
        """TODO implement sum bar"""
        if not hasattr(self, "wb_write_count"):
            self.wb_write_count = 0
        write_count = self.wb_write_count
        word_size = OPTS.alu_word_size

        super().wb(addr, src, cond)
        if src == "add":
            new_src = "data_in"
            cin = self.cin
            if self.sram.alu_num_words == 1:
                cin = cin[:-1]
            if write_count == 0:
                data_one_, data_two, data_three = self.data_one, self.data_two, self.data_three
                mask = self.mask_three
                data_one = [data_three[i] if mask[i] else data_one_[i] for i in range(len(data_one_))]
            else:
                data_one, data_two = self.data_two, self.wb_prev_c_data

            expectation = alu_sum(data_one, data_two, list(reversed(cin)),
                                  word_size, OPTS.serial)
            sum_vec = list(itertools.chain.from_iterable([x[0] for x in expectation]))
            sum_vec_bar = [int(not x) for x in sum_vec]
            self.wb_prev_c_data = sum_vec

            self.data = list(reversed(sum_vec_bar))

            #  set data for sum_bar

        else:
            bar_map = {"and": "nand", "or": "nor", "xnor": "xor"}
            bar_map.update({value: key for key, value in bar_map.items()})
            new_src = bar_map[src]
        super().wb(addr + 1, new_src, cond)
        self.wb_write_count += 1

    def setup_read_measurements(self, address_int, expected_data=None):
        self.has_read_measurements = True
        super().setup_read_measurements(address_int, expected_data)

    def rd(self, addr):
        if addr % 2 == 1:
            assert False, "Odd addresses should not be read directly"
        super().rd(addr)
        adjacent_address = addr + 1
        if self.has_read_measurements:
            self.setup_read_measurements(adjacent_address)
        self.force_select_nor = True
        super().rd(adjacent_address)
        self.has_read_measurements = False
        self.force_select_nor = False

    def set_selects(self, bus_sel=None, sr_in=None, sr_out=None):
        if self.force_select_nor:
            bus_sel = "s_nor"
        super().set_selects(bus_sel, sr_in, sr_out)

    def get_precharge_probe(self, bitline_name, bank, col):
        col = int(col / 2)
        return self.probe.voltage_probes[bitline_name][bank][col]

    def finalize_sim_file(self):
        self.stim.replace_bitcell(self)
        super().finalize_sim_file()

    def write_ic(self, ic, col_node, col_voltage):
        phi = 0.1 * OPTS.llg_prescale
        theta = math.acos(col_voltage) * OPTS.llg_prescale
        theta_2 = math.acos(-col_voltage) * OPTS.llg_prescale
        full_match, row, col = re.findall(r"(Xbit_r([0-9]+)_c([0-9]+))", col_node)[0]
        row, col = int(row), int(col)
        if col % 2 == 1:
            return
        col = int(col / 2)
        col_node = col_node.replace(full_match, f"Xbit_r{row}_c{col}")

        phi_node = col_node.replace(".state", ".phi")
        theta_node = col_node.replace(".state", ".theta")
        theta_2_node = theta_node.replace("X0.theta", "X1.theta")
        phi_2_node = phi_node.replace("X0.phi", "X1.phi")
        for node, value in zip([theta_node, theta_2_node, phi_node, phi_2_node],
                               [theta, theta_2, phi, phi]):
            ic.write(".ic V({})={} \n".format(node, value))
