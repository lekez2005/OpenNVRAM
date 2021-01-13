import os
import subprocess

try:
    from script_loader import load_setup
except ImportError:
    from .script_loader import load_setup

setup, tech_name = load_setup()

cellviews = ["cell_6t", "sense_amp", "write_driver", "ms_flop", "replica_cell_6t", "tri_gate",
             "addr_ff", "clock_nor", "dinv", "inv_clk", "inv_nor", "nor_1",
             "out_inv_16", "output_latch", "addr_latch", "cell_10t",
             "dinv_mx", "inv_col", "mux_a", "nor_1_mx", "out_inv_2", "precharge",
             "tgate", "inv", "inv_dec", "mux_abar", "out_inv_4"]
cellviews = ["cell_6t_wide_pins"]

log_file = os.environ["SCRATCH"] + "/logs/strmOut.log"
dirname = os.path.abspath(os.path.dirname(__file__))
tech_folder = os.path.abspath(os.path.abspath("{0}/..".format(dirname)))
out_dir = os.path.join(os.environ.get("OPENRAM_TECH"), tech_name, "gds_lib")
library = setup.import_library_name

for cellview in cellviews:
    layout_file_path = os.path.join(setup.cadence_work_dir, library, cellview, "layout/layout.oa")
    if os.path.isfile(layout_file_path) or True:
        command = [
            "strmout",
            "-layerMap", setup.layer_map,
            "-library", library,
            "-view", "layout",
            "-strmFile", cellview + ".gds",
            "-topCell", cellview,
            "-runDir", setup.cadence_work_dir,
            "-logFile", log_file,
            "-outputDir", out_dir
        ]
        if hasattr(setup, 'objectMap'):
            command.extend(["-objectMap", getattr(setup, "objectMap")])
        retcode = subprocess.call(command, cwd=setup.cadence_work_dir)
        if retcode != 0:
            print("Error exporting {}".format(cellview))
            print(command)
