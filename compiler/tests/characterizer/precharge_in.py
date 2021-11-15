#!/usr/bin/env python3
import os
from glob import glob

from char_test_base import CharTestBase
from distributed_load_base import DistributedLoadMixin


class PrechargeIn(DistributedLoadMixin, CharTestBase):
    instantiate_dummy = False

    @classmethod
    def add_additional_options(cls):
        cls.parser.add_argument("--size", default=None, type=int)
        cls.parser.add_argument("--max_size",
                                default=10, type=float, help="max precharge size")
        cls.parser.add_argument("--num_sizes",
                                default=10, type=int, help="Number of sizes to sweep")
        cls.parser.add_argument("--precharge_array", default=None)
        cls.parser.add_argument("-l", "--load", default=30e-15, type=float,
                                help="Capacitive load for resistance measurement")

    def setUp(self):
        super().setUp()
        self.set_cell_mod()

    def get_file_suffixes(self, _):
        from tech import parameter
        return [("beta", parameter["beta"])]

    def set_cell_mod(self):
        from globals import OPTS
        OPTS.precharge_array = self.options.precharge_array or OPTS.precharge_array

    def get_cell_name(self) -> str:
        if not hasattr(self, "sample_array"):
            self.sample_array = self.create_class_from_opts("precharge_array", columns=32)
        return self.sample_array.pc_cell.get_char_data_name()

    def get_pins(self):
        return self.sample_array.get_input_pins()

    def make_dut(self, num_elements):
        load = self.create_class_from_opts("precharge_array", size=self.options.size,
                                           columns=num_elements)
        return load

    def get_dut_instance_statement(self, pin):
        pins = [x for x in self.load.pins]
        pins[pins.index(pin)] = "d"
        pins_str = " ".join(pins)

        dut_instance = "X4 {} {} \n".format(pins_str, self.load.name)
        return dut_instance

    def measure_resistance(self):
        import debug
        from base.design import design
        from characterization_utils import get_measurement_threshold, TEN_FIFTY_THRESH
        from measure_resistance import MeasureResistance

        self.vdd_value = vdd_value = self.corner[1]
        size = self.options.size
        self.options.method = TEN_FIFTY_THRESH

        thresholds = get_measurement_threshold(TEN_FIFTY_THRESH, vdd_value)
        rise_start, rise_end, fall_start, fall_end = thresholds
        c_load = size * self.options.load
        period = self.options.period * size

        # create precharge array
        cell_name = self.get_cell_name()
        design.name_map.clear()  # to prevent GDS uniqueness errors
        precharge_array = self.create_class_from_opts("precharge_array", size=self.options.size,
                                                      columns=32)
        self.precharge = precharge_array.pc_cell
        # force re-run
        self.run_pex = True
        buffer_pex = self.run_pex_extraction(self.precharge, self.precharge.name,
                                             run_drc=self.options.run_drc_lvs,
                                             run_lvs=self.options.run_drc_lvs)

        bl_res = []
        br_res = []

        for pin in self.sample_array.get_input_pins():
            dut_instance = self.get_measurement_instance(pin, c_load)

            args = {
                "dut_instance": dut_instance,
                "vdd_value": vdd_value,
                "PERIOD": period,
                "TEMPERATURE": self.corner[2],
                "half_vdd": 0.5 * vdd_value,
                "meas_delay": "0.3n",
                "Cload": c_load,
                "rise_start": rise_start,
                "rise_end": rise_end,
                "fall_start": fall_start,
                "fall_end": fall_end
            }

            res = MeasureResistance.generate_and_run(self, size, buffer_pex, c_load, args)
            r_n, r_p, fall_time, rise_time, scale_factor = res
            res = [x for x in [r_n, r_p] if x is not None]
            if pin in ["en", "precharge_en_bar", "discharge"]:
                bl_res.extend(res)
                if "br_reset" not in self.sample_array.get_input_pins():
                    br_res.extend(res)
            elif pin == "bl_reset":
                bl_res.extend(res)
            else:
                br_res.extend(res)

        for pin_name, all_res in zip(["bl", "br"], [bl_res, br_res]):
            res = max(all_res)
            debug.info(0, "{} = {}".format(pin_name, res))
            self.save_result(cell_name, "resistance_{}".format(pin_name), res, size=size,
                             size_suffixes=[],
                             file_suffixes=self.get_file_suffixes(None))

    def get_measurement_instance(self, pin_name, c_load):

        target_pin = "bl"
        discharge = "0"

        if pin_name in ["en", "precharge_en_bar"]:
            initial_cond = "0"
            en = "v_fall"
            bl_reset = br_reset = "0"
        elif pin_name == "bl_reset":
            initial_cond = self.vdd_value
            bl_reset = br_reset = "a"
            en = "vdd"
        elif pin_name == "br_reset":
            initial_cond = self.vdd_value
            bl_reset = "0"
            en = "vdd"
            br_reset = "a"
            target_pin = "br"
        elif pin_name == "discharge":
            initial_cond = self.vdd_value
            en = discharge = "vdd"
            bl_reset = br_reset = "0"
        else:
            raise ValueError("Invalid pin: {}".format(pin_name))
        other_pin = "br" if target_pin == "bl" else "bl"
        pins = [x for x in self.precharge.pins]

        nets = [en, bl_reset, br_reset, discharge]
        for i, pin_name in enumerate(["en", "bl_reset", "br_reset", "discharge"]):
            if pin_name in pins:
                pins[pins.index(pin_name)] = nets[i]

        pins[pins.index(target_pin)] = "out_bar"
        pins[pins.index(other_pin)] = "out"

        netlist = f"""
        Vfall v_fall gnd pulse {self.vdd_value} 0 0ps 20ps 20ps '0.5*PERIOD' 'PERIOD'
        Xdut {" ".join(pins)} {self.precharge.name}
        cdelay2 out gnd '{c_load}' 
        .ic V(out_bar) = {initial_cond}
        .ic V(out) = {initial_cond}
        """
        return netlist

    def test_sweep(self):
        import debug
        from globals import OPTS
        if self.options.size:
            sizes = [self.options.size]
        else:
            import numpy as np
            sizes = np.linspace(1, self.options.max_size, self.options.num_sizes)

        default_max_c = self.options.max_c
        default_min_c = self.options.min_c
        default_period = self.options.period

        # sizes = [10]
        self.default_cols = [1]

        for size in sizes:
            debug.info(0, "\tSize = %g", size)
            self.options.size = size
            self.options.max_c = default_max_c * size / sizes[0]
            self.options.min_c = default_min_c * size / sizes[0]
            self.options.period = default_period
            try:
                super().test_sweep()
                self.measure_resistance()
            except AssertionError as ex:
                if str(ex) == "Optimization result not found":
                    debug.warning("%s for size %g", ex, size)
            temp_files = glob(OPTS.openram_temp + "/wrapped*")
            for file in temp_files:
                #pass
                os.remove(file)


PrechargeIn.run_tests(__name__)
