from random import randint

from modules.cam.cam_dut import CamDut
from modules.cam.cam_probe import CamProbe
from characterizer import SpiceCharacterizer
from characterizer.simulation.sim_operations_mixin import FALL, CROSS, RISE
from globals import OPTS


class CamSpiceCharacterizer(SpiceCharacterizer):
    def configure_timing(self, sram):
        super().configure_timing(sram)
        self.search_period = self.read_period
        self.search_duty_cycle = self.read_duty_cycle

    def create_probe(self):
        self.probe = CamProbe(self.sram, OPTS.pex_spice)

    def create_dut(self):
        dut = CamDut(self.sf, self.corner)
        dut.words_per_row = self.words_per_row
        return dut

    def get_saved_nodes(self):
        dout_probes = []
        for _, values in self.dout_probes.items():
            dout_probes.extend(values.values())
        return list(sorted(list(self.probe.saved_nodes) +
                           dout_probes +
                           list(self.probe.data_in_probes.values()) +
                           list(self.mask_probes.values())))

    def get_ml_probe(self, bank, row):
        return self.probe.ml_probes[bank][row]

    def test_address(self, address, bank=None, dummy_address=None, data=None, mask=None):
        test_data = self.normalize_test_data(address, bank, dummy_address, data, mask)
        address, bank, dummy_address, data, mask, data_bar = test_data

        off_by_one = [x for x in data]
        off_by_one[-1] = int(not off_by_one[-1])

        zero_mask = [0] * self.sram.word_size
        # discharge all matchlines with zero mask
        self.search_data(data_bar, zero_mask)

        for d in [data, data_bar]:
            off_by_one = [x for x in d]
            off_by_one[-1] = int(not off_by_one[-1])

            self.setup_write_measurements(address)
            self.write_address(address, d, mask)

            # should match
            self.setup_search_measurements(address)
            self.search_data(d, mask)
            # off by one mismatch
            self.setup_search_measurements(address)
            self.search_data(off_by_one, mask)

    def generate_energy_op(self, op_index):
        mask = [1] * self.word_size
        address = randint(0, self.sram.num_words - 1)
        ops = ["search", "write"]
        op = ops[op_index % 2]

        data = [randint(0, 1) for _ in range(self.word_size)]
        if op == "search":
            self.search_data(data, mask)
        else:
            self.write_address(address, data, mask)
        return op

    def search_data(self, data_v, mask_v):
        self.command_comments.append(f"* [{self.current_time: >20}] search {data_v} "
                                     f"mask {mask_v}\n")
        self.mask = list(reversed(mask_v))
        self.data = list(reversed(data_v))

        self.chip_enable = 1
        self.read = 1

        self.duty_cycle = self.search_duty_cycle
        self.period = self.search_period

        self.update_output()

    def generate_delay_measurements(self, meas_prefix, trig_probes, probes, rows=None,
                                    trig_thresh=None, targ_thresh=None,
                                    trig_dir=FALL, targ_dir=CROSS):
        if rows is None:
            rows = list(range(self.sram.bank.num_rows))
        if trig_thresh is None:
            trig_thresh = 0.5 * self.vdd_voltage
        if targ_thresh is None:
            targ_thresh = trig_thresh

        time_suffix = self.get_time_suffix()

        for bank in range(self.sram.num_banks):
            bank_suffix = "" if self.sram.num_banks == 1 else f"_b{bank}"

            for row in rows:
                if isinstance(trig_probes, dict):
                    trig_probe = trig_probes[bank]
                else:
                    trig_probe = trig_probes(bank, row)
                meas_name = f"{meas_prefix}_DELAY{bank_suffix}_r{row}_t{time_suffix}"
                if isinstance(probes, dict):
                    probe = probes[bank][row]
                else:
                    probe = probes(bank, row)
                self.stim.gen_meas_delay(meas_name=meas_name,
                                         trig_name=trig_probe,
                                         trig_val=trig_thresh, trig_dir=trig_dir,
                                         trig_td=self.current_time,
                                         targ_name=probe,
                                         targ_val=targ_thresh, targ_dir=targ_dir,
                                         targ_td=self.current_time)

    def setup_search_measurements(self, target_address):
        self.period = self.search_period
        self.duty_cycle = self.search_duty_cycle
        bank_index, _, row, col_index = self.probe.decode_address(target_address)
        self.sf.write(f"* -- Search : [{target_address}, {row}, {col_index},"
                      f" {bank_index}, {self.current_time},"
                      f" {self.search_period}, {self.search_duty_cycle}]\n")
        self.setup_ml_precharge_measurements()
        self.generate_power_measurement("SEARCH")

        self.generate_delay_measurements("SEARCH_DELAY", self.probe.clk_probes,
                                         self.probe.dout_probes,
                                         trig_dir=FALL, targ_dir=CROSS)
        if self.measure_slew:
            def trig_probes(bank_, row_):
                return self.probe.dout_probes[bank_, row_]

            self.generate_delay_measurements("SEARCH", trig_probes,
                                             self.probe.dout_probes,
                                             trig_thresh=0.1 * self.vdd_voltage,
                                             targ_thresh=0.9 * self.vdd_voltage,
                                             trig_dir=RISE, targ_dir=RISE)

    def setup_ml_precharge_measurements(self):
        self.generate_delay_measurements("PRECHARGE", self.probe.clk_probes,
                                         self.probe.ml_probes,
                                         targ_thresh=0.9 * self.vdd_voltage,
                                         trig_dir=RISE, targ_dir=RISE)
