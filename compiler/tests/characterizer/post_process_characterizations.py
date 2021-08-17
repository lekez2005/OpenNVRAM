#!/usr/bin/env python3
"""
Save and plot convex fit for inverters and precharges used in ControlBufferOptimizer
New bank classes using different inverter/precharge types should add a config option
"""
import argparse
import json
import os

from char_test_base import CharTestBase
from characterization_utils import parse_options

SHARED_BASELINE = "shared_baseline"
SHARED_SOTFET = "shared_sotfet"
PUSH = "push"

configs = {
    SHARED_BASELINE: "../shared_decoder/config_shared_baseline_{}.py",
    SHARED_SOTFET: "../shared_decoder/config_shared_sotfet_{}.py",
    PUSH: "../push_rules/config_push_hs_{}.py"
}

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", default=SHARED_BASELINE, type=str)
parser.add_argument("-l", "--log_plot", action="store_true")
parser.add_argument("--num_sizes", default=30, type=float, help="Number of sizes to use")

options = parse_options(parser)
config_template = options.config
if config_template in configs:
    config_template = configs[config_template]
if not os.path.isabs(config_template):
    config_template = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                   config_template))


class PostProcessInverter(CharTestBase):
    config_template = config_template

    def test_cmos_bank(self):
        from modules.baseline_bank import BaselineBank
        self.post_process_bank_modules(BaselineBank)

    def post_process_bank_modules(self, bank_class, **kwargs):
        import numpy as np
        from scipy import interpolate
        from characterizer.characterization_data import load_json_file

        bank = self.create_bank(bank_class, **kwargs)
        optimizer = bank.optimizer

        unique_config_keys = optimizer.unique_config_keys

        def numpy_to_list(x_y_data):
            return {key: [np.array(x).tolist() for x in val] for key, val in x_y_data.items()}

        for key in unique_config_keys.keys():
            config = unique_config_keys[key]["config"]
            class_name, suffix_key, buffer_mod, in_pin, out_pin, max_buffer_size = config

            convex_data = unique_config_keys[key]["convex_data"]
            data = unique_config_keys[key]["data"]

            data_file = os.path.join(self.get_char_data_file("curve_fit"), class_name + ".json")
            existing_data = load_json_file(data_file)
            if suffix_key not in existing_data:
                existing_data[suffix_key] = {}
            existing_data[suffix_key]["convex_data"] = numpy_to_list(convex_data)
            existing_data[suffix_key]["data"] = numpy_to_list(data)

            with open(data_file, "w") as f:
                json.dump(existing_data, f, indent=2)

        if self.options.plot:
            import matplotlib.pylab as plt
            for key in unique_config_keys.keys():
                convex_data = unique_config_keys[key]["convex_data"]
                data = unique_config_keys[key]["data"]
                spline_fit = unique_config_keys[key]["spline"]

                keys = list(data.keys())

                fig, subplots = plt.subplots(ncols=1, nrows=len(keys), sharex=True)
                for i in range(len(keys)):
                    plot_func = subplots[i].semilogx if options.log_plot else subplots[i].plot
                    plot_func = subplots[i].loglog
                    data_key = keys[i]
                    # plot_func(convex_data[data_key][0],
                    #           convex_data[data_key][1], '-o')
                    sizes = data[data_key][0]
                    plot_func(sizes, data[data_key][1], '+',
                              markersize=4)
                    x_data = np.linspace(sizes[0], sizes[-1], 100)
                    y_data = interpolate.splev(x_data, spline_fit[data_key], der=0)
                    plot_func(x_data, y_data, '-')

                    subplots[i].set_ylabel(data_key)
                fig.suptitle(key, fontsize=12)
                if self.options.save_plot:
                    plot_file = os.path.join(self.get_char_data_file("curve_fit"),
                                             key + ".png")
                    plt.savefig(plot_file)
                else:
                    plt.show()

    @staticmethod
    def create_bank(bank_class, **kwargs):
        bank = bank_class(word_size=32, num_words=128, words_per_row=2,
                          name="bank1", **kwargs)
        return bank


PostProcessInverter.run_tests(__name__)
