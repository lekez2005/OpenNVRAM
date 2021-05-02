#!/bin/env python

import os
import subprocess
import sys

sys.path.append(os.path.dirname(__file__))
try:
    from script_loader import load_setup
except (ImportError, ModuleNotFoundError):
    from .script_loader import load_setup


def export_gds(gds, top_level=False):
    setup, _ = load_setup(top_level=top_level)

    command = [
        "strmin",
        "-layerMap", setup.layer_map,
        "-library",  setup.export_library_name,
        "-strmFile", gds,
        "-attachTechFileOfLib", setup.pdk_library_name,
        "-logFile", os.environ["SCRATCH"] + "/logs/strmIn.log",
        "-view", "layout"
    ]

    subprocess.call(command, cwd=setup.cadence_work_dir)


def latest_scratch(scratch):
    all_subdirs = [scratch + d for d in os.listdir(scratch) if os.path.isdir(scratch + d)]
    return max(all_subdirs, key=os.path.getmtime)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        export_gds(sys.argv[1], top_level=True)
    else:
        scratch = os.path.join(os.environ["SCRATCH"], "openram")
        export_gds(os.path.join(latest_scratch(scratch), "/temp.gds"), top_level=False)
