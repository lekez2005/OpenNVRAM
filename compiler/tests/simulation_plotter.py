import re
from abc import ABC

import debug
from characterizer import SpiceReader


class Plotter(ABC):
    def finalize_plots(self, title, from_t, to_t):
        raise NotImplementedError

    def plot(self, signal_name, legend_name, from_t=None, to_t=None):
        raise NotImplementedError

    def plot_current(self, signal_name, legend_name, from_t=None, to_t=None):
        raise NotImplementedError


class MatPlotLibPlotter(Plotter):
    def __init__(self, sim_data: SpiceReader):
        self.sim_data = sim_data
        self.initialize_matplotlib()

    def initialize_matplotlib(self):
        import logging
        import matplotlib
        matplotlib.use("Qt5Agg")
        from matplotlib import pyplot as plt
        logging.getLogger('matplotlib').setLevel(logging.WARNING)
        _, self.ax1 = plt.subplots()

    def finalize_plots(self, title, from_t, to_t):
        from matplotlib import pyplot as plt
        plt.axhline(y=0.5 * self.sim_data.vdd, linestyle='--', linewidth=0.5)
        plt.axhline(y=self.sim_data.vdd, linestyle='--', linewidth=0.5)

        plt.title(title)
        self.ax1.grid()
        self.ax1.legend(loc="center left", fontsize="x-small")
        plt.show()

    def plot(self, signal_name, legend_name, from_t=None, to_t=None):
        signal = self.sim_data.get_signal_time(signal_name,
                                               from_t=from_t, to_t=to_t)
        self.ax1.plot(*signal, label=legend_name)

    def plot_current(self, signal_name, legend_name, from_t=None, to_t=None):
        current_time = self.sim_data.get_signal_time(signal_name,
                                                     from_t=from_t, to_t=to_t)
        current = current_time[1] * 1e6
        ax2 = self.ax1.twinx()

        ax2.plot(current_time[0], current, ':k', label="current")
        ax2.set_ylabel("Current (uA)")
        ax2.legend()


class CadencePlotter(Plotter):
    def __init__(self, data_dir, new_plot=False, clear_plot=True,
                 workspace_id=None):
        self.new_plot = new_plot
        self.clear_plot = clear_plot
        try:
            from skillbridge import Workspace
            self.ws = Workspace.open(workspace_id=workspace_id)
            self.data_dir = data_dir
            self.load_plot_window()
        except ImportError:
            debug.error("Error importing skillbridge")

    def load_plot_window(self):
        """Create/Access Cadence plot window ID"""
        if self.new_plot:
            self.skill_plot_id = self.ws.awv.create_plot_window()
        else:
            self.skill_plot_id = self.ws.awv.get_current_window()
        # print(self.skill_plot_id)
        if self.skill_plot_id is None:
            self.skill_plot_id = self.ws.awv.create_plot_window()
        if self.clear_plot:
            self.ws.awv.clear_plot_window(self.skill_plot_id)
        assert self.ws.rdb.load_results("unbound", self.data_dir), \
            "Loading Cadence results failed"

    def plot(self, signal_name, legend_name, from_t=None, to_t=None):
        plot_expression = f"v(\"{signal_name}\", ?result \"tran-tran\" ?resultsDir \"{self.data_dir}\")"
        if legend_name is None:
            legend_name = self.get_plot_name(signal_name)
        # self.ws.awv.simple_plot_expression(self.skill_plot_id, f"VT(\"vdd\"", None, None, expr=["vdd3"])
        return self.ws.awv.simple_plot_expression(self.skill_plot_id, plot_expression, None, None,
                                                  expr=[legend_name])

    def plot_current(self, signal_name, legend_name, from_t=None, to_t=None):
        self.plot(signal_name, legend_name, from_t, to_t)

    @staticmethod
    def get_plot_name(signal_name):
        """Get legend to use based on full net"""
        from globals import OPTS
        if OPTS.use_pex:
            plot_name = signal_name
            for prefix in ["_Xbank[0-9]+", "Xrow_decoder"]:
                if len(re.findall(prefix, plot_name)) == 2:
                    plot_name = re.split(prefix, plot_name)[1]
                plot_name = re.split(prefix, plot_name)[0]
            if plot_name.startswith("v("):
                plot_name = plot_name[2:]
            if plot_name.startswith("_"):
                plot_name = plot_name[1:]

            plot_name = plot_name.replace("Xsram.N_", "")
            plot_name = plot_name.split("_X")[-1]
        else:
            plot_name = signal_name.split(".")[-1].replace(")", "")
        return plot_name

    def finalize_plots(self, title, from_t, to_t):
        if from_t is not None and to_t is not None:
            self.ws.awv.zoom_graph_x(self.skill_plot_id, [from_t, to_t])
        self.ws.awv.display_subwindow_title(self.skill_plot_id, title)
