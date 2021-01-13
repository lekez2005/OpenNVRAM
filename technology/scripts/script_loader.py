import argparse
import importlib.util
import os


def load_setup():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--tech", dest="tech_name", help="Technology name",
                        default=os.environ.get("OPENRAM_TECH_NAME"))
    options, _ = parser.parse_known_args()

    tech_directory = os.environ.get("OPENRAM_TECH")
    tech_name = options.tech_name
    setup_path = "{0}/setup_scripts/setup_openram_{1}.py".format(tech_directory, tech_name)
    spec = importlib.util.spec_from_file_location("setup", setup_path)
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    return setup, tech_name
