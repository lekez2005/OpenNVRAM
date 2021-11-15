from importlib import reload
from typing import List, Tuple


class DistributedLoadMixin:

    default_cols = [1, 4, 8, 16, 32, 64, 128]
    fixed_pins = None  # pins that do not scale with cols

    @staticmethod
    def load_module_from_str(module_name):
        module = reload(__import__(module_name))
        mod_class = getattr(module, module_name)
        return mod_class

    def get_pins(self) -> List[str]:
        pass

    def get_cell_name(self) -> str:
        pass

    def make_dut(self, num_elements):
        pass

    def get_dut_instance_statement(self, pin) -> str:
        pass

    def get_size_suffixes(self, num_elements):
        return [("cols", num_elements), ("wire", self.load.wire_length)]

    def get_file_suffixes(self, num_elements) -> List[Tuple[str, float]]:
        pass

    def test_plot(self):
        if not self.options.plot:
            return
        self.plot_results(self.get_cell_name(), self.get_pins(),
                          scale_by_x=self.options.scale_by_x, show_legend=True,
                          sweep_variable="cols", save_plot=self.options.save_plot)

    def test_sweep(self):
        if self.options.plot:
            return

        import debug
        from characterization_utils import wrap_cell, search_meas
        from base.design import design

        self.set_temp_folder(self.get_cell_name())

        self.driver_wire_length = self.options.driver_wire_length

        default_max_c = self.options.max_c
        default_min_c = self.options.min_c
        default_period = self.options.period

        total_cap = self.options.max_c

        fixed_pins = self.fixed_pins or []

        for pin in self.get_pins():
            debug.info(0, "Pin = %s", pin)

            self.dut_pin = pin

            self.options.max_c = default_max_c
            self.options.min_c = default_min_c
            self.options.period = default_period

            all_cols = [1] if pin in fixed_pins else self.default_cols

            for i in range(len(all_cols)):
                cols = all_cols[i]
                if i > 0:
                    self.options.max_c = (2 * total_cap * self.default_cols[i] /
                                          self.default_cols[i - 1])
                    self.options.min_c = 0.5 * total_cap
                    meas_file = self.stim_file_name.replace(".sp", ".measure")
                    previous_fall = float(search_meas("invf", meas_file))
                    self.options.period = default_period + previous_fall * 4

                design.name_map.clear()  # to prevent GDS uniqueness errors

                load = self.make_dut(cols)

                # some cell names are not unique by num_cols specified
                # so wrap based on both num_cols and wire_length
                load = wrap_cell(load, pin, self.driver_wire_length,
                                 name_suffix="_n{}".format(cols))

                self.load = load

                self.load_pex = self.run_pex_extraction(load, load.name)

                self.dut_name = load.name

                self.dut_instance = self.get_dut_instance_statement(pin)

                self.run_optimization()
                total_cap = self.get_optimization_result()
                size = getattr(self.options, "size", 1)
                cap_per_stage = total_cap / cols / size

                debug.info(0, "\t Cols = %4s, caps = %g", cols, cap_per_stage)
                self.save_result(self.get_cell_name(), pin, cap_per_stage, size=size,
                                 size_suffixes=self.get_size_suffixes(cols),
                                 file_suffixes=self.get_file_suffixes(cols))
