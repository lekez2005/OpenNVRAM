import debug
from characterizer import SpiceCharacterizer
from characterizer.net_probes.sram_probe import SramProbe
from globals import OPTS
from modules.reram.reram_spice_dut import ReramSpiceDut


class ReramProbe(SramProbe):
    def probe_address(self, address, pin_name="q"):
        probe_node = OPTS.state_probe_node
        for i in range(self.sram.word_size):
            self.dout_probes[i] = "DATA_OUT[{}]".format(i)
        super().probe_address(address, pin_name=probe_node)

    def probe_bank_currents(self, bank):
        pass

    def probe_address_currents(self, address):
        pass

    def get_sense_amp_internal_nets(self):
        return ["dout", "vdata", "bl"]

    def get_bitcell_current_nets(self):
        return ["be"]


class ReramSpiceCharacterizer(SpiceCharacterizer):
    def create_dut(self):
        stim = ReramSpiceDut(self.sf, self.corner)
        stim.words_per_row = self.sram.words_per_row
        return stim

    def test_address(self, address, bank=None, dummy_address=None, data=None, mask=None):
        test_data = self.normalize_test_data(address, bank, dummy_address, data, mask)
        address, bank, dummy_address, data, mask, data_bar = test_data

        debug.info(2, "Dummy address = %d", dummy_address)

        # initial read to charge up nodes

        for data, data_bar in [(data, data_bar), (data_bar, data)]:
            self.setup_write_measurements(address)
            self.write_address(address, data_bar, mask)
            # reset bitlines, vdata
            self.setup_write_measurements(dummy_address)
            self.write_address(dummy_address, data, mask)
            self.setup_read_measurements(dummy_address)
            self.read_address(dummy_address)
            self.setup_read_measurements(address)
            self.read_address(address)

    def write_ic(self, ic, col_node, col_voltage):
        # TODO setting IC is model dependent
        return
        # vdd = self.vdd_voltage
        # if col_voltage > 0.5 * vdd:
        #     col_voltage = OPTS.min_filament_thickness
        # else:
        #     col_voltage = OPTS.max_filament_thickness
        # ic.write(".ic V({})={} \n".format(col_node, col_voltage))

    def create_probe(self):
        self.probe = ReramProbe(self.sram, OPTS.pex_spice)
