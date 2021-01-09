#!/bin/env python

import importlib.util
import os, sys
import subprocess


def export_gds(gds):
    tech_directory = os.environ.get("OPENRAM_TECH")
    tech_name = os.environ.get("OPENRAM_TECH_NAME")
    setup_path = "{0}/setup_scripts/setup_openram_{1}.py".format(tech_directory, tech_name)
    spec = importlib.util.spec_from_file_location("setup", setup_path)
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)

    command = [
        "strmin",
        "-layerMap", setup.layer_map,
        "-library", setup.export_library_name,
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
        export_gds(sys.argv[1])
    else:
        scratch = os.path.join(os.environ["SCRATCH"], "openram")
        export_gds(os.path.join(latest_scratch(scratch), "/temp.gds"))
