"""
This is called globals.py, but it actually parses all the arguments and performs
the global OpenRAM setup as well.
"""
import importlib.util
import optparse
import copy
import os
import re
import shutil
import sys
from importlib import reload

import debug
import options

USAGE = "Usage: openram.py [options] <config file>\nUse -h for help.\n"

# Anonymous object that will be the options
OPTS = options.options()
DEFAULT_OPTS = options.options()

def parse_args():
    """ Parse the optional arguments for OpenRAM """

    global OPTS

    option_list = {
        optparse.make_option("-b", "--backannotated", action="store_true", dest="run_pex",
                             help="Back annotate simulation"),
        optparse.make_option("-o", "--output", dest="output_name",
                             help="Base output file name(s) prefix", metavar="FILE"),
        optparse.make_option("-p", "--outpath", dest="output_path",
                             help="Output file(s) location"),
        optparse.make_option("-n", "--nocheck", action="store_false",
                             help="Disable inline LVS/DRC checks", dest="check_lvsdrc"),
        optparse.make_option("-v", "--verbose", action="count", dest="debug_level",
                             help="Increase the verbosity level"),
        optparse.make_option("-t", "--tech", dest="tech_name",
                             help="Technology name"),
        optparse.make_option("-s", "--spice", dest="spice_name",
                             help="Spice simulator executable name"),
        optparse.make_option("-r", "--remove_netlist_trimming", action="store_false", dest="trim_netlist",
                             help="Disable removal of noncritical memory cells during characterization"),
        optparse.make_option("-c", "--characterize", action="store_false", dest="analytical_delay",
                             help="Perform characterization to calculate delays (default is analytical models)"),
        optparse.make_option("-d", "--dontpurge", action="store_false", dest="purge_temp",
                             help="Don't purge the contents of the temp directory after a successful run")
        # -h --help is implicit.
    }

    parser = optparse.OptionParser(option_list=option_list,
                                   description="Compile and/or characterize an SRAM.",
                                   usage=USAGE,
                                   version="OpenRAM")

    (options, args) = parser.parse_args(values=OPTS)
    # If we don't specify a tech, assume freepdk45.
    # This may be overridden when we read a config file though...
    if OPTS.tech_name == "":
        OPTS.tech_name = "freepdk45"
    # Alias SCMOS to AMI 0.5um
    if OPTS.tech_name == "scmos":
        OPTS.tech_name = "scn3me_subm"
    global DEFAULT_OPTS
    DEFAULT_OPTS = copy.deepcopy(OPTS)

    return (options, args)

def print_banner():
    """ Conditionally print the banner to stdout """
    global OPTS
    if OPTS.is_unit_test:
        return

    debug.print_str("|==============================================================================|")
    name = "OpenRAM Compiler"
    debug.print_str("|=========" + name.center(60) + "=========|")
    debug.print_str("|=========" + " ".center(60) + "=========|")
    debug.print_str("|=========" + "VLSI Design and Automation Lab".center(60) + "=========|")
    debug.print_str("|=========" + "University of California Santa Cruz CE Department".center(60) + "=========|")
    debug.print_str("|=========" + " ".center(60) + "=========|")
    debug.print_str("|=========" + "VLSI Computer Architecture Research Group".center(60) + "=========|")
    debug.print_str("|=========" + "Oklahoma State University ECE Department".center(60) + "=========|")
    debug.print_str("|=========" + " ".center(60) + "=========|")
    user_info = "Usage help: openram-user-group@ucsc.edu"
    debug.print_str("|=========" + user_info.center(60) + "=========|")
    dev_info = "Development help: openram-dev-group@ucsc.edu"
    debug.print_str("|=========" + dev_info.center(60) + "=========|")
    temp_info = "Temp dir: {}".format(OPTS.openram_temp)
    debug.print_str("|=========" + temp_info.center(60) + "=========|")
    debug.print_str("|==============================================================================|")


def check_versions():
    """ Run some checks of required software versions. """

    # Now require python >=3.6
    major_python_version = sys.version_info.major
    minor_python_version = sys.version_info.minor
    if not (major_python_version == 3 and minor_python_version >= 6):
        debug.error("Python 3.6 or greater is required.", -1)

    # FIXME: Check versions of other tools here??
    # or, this could be done in each module (e.g. verify, characterizer, etc.)


def init_openram(config_file, is_unit_test=True, openram_temp=None):
    """Initialize the technology, paths, simulators, etc."""
    # reset options to default since some tests modify OPTS
    for key in list(OPTS.__dict__.keys()):
        if key not in DEFAULT_OPTS.__dict__:
            del OPTS.__dict__[key]
        else:
            OPTS.__dict__[key] = DEFAULT_OPTS.__dict__[key]

    if openram_temp is not None:
        OPTS.set_temp_folder(openram_temp)

    check_versions()

    debug.info(1,"Initializing OpenRAM...")

    read_config(config_file, is_unit_test, openram_temp)

    debug.setup_file_log(OPTS.log_file)

    setup_paths()

    import_tech()

    initialize_classes()


def get_tool(tool_type, preferences):
    """
    Find which tool we have from a list of preferences and return the
    one selected and its full path.
    """
    debug.info(2,"Finding {} tool...".format(tool_type))

    for name in preferences:
        exe_name = find_exe(name)
        if exe_name != None:
            debug.info(1, "Using {0}: {1}".format(tool_type,exe_name))
            return(name,exe_name)
        else:
            debug.info(1, "Could not find {0}, trying next {1} tool.".format(name,tool_type))
    else:
        return(None,"")


def read_config(config_file, is_unit_test=True, openram_temp=None):
    """ 
    Read the configuration file that defines a few parameters. The
    config file is just a Python file that defines some config
    options. 
    """
    global OPTS
    
    # Create a full path relative to current dir unless it is already an abs path
    if not os.path.isabs(config_file):
        config_file = os.path.join(os.getcwd(), config_file)
    # Expand the user if it is used
    config_file = os.path.expanduser(config_file)
    # Import the configuration file of which modules to use
    debug.info(1, "Configuration file is " + config_file)
    try:
        if os.path.exists(config_file):
            spec = importlib.util.spec_from_file_location("config_file")
            config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config)
        else:
            config = importlib.import_module(os.path.basename(config_file))
    except:
        debug.error("Unable to read configuration file: {0}".format(config_file), 2)

    for k,v in config.__dict__.items():
        # The command line will over-ride the config file
        # except in the case of the tech name! This is because the tech name
        # is sometimes used to specify the config file itself (e.g. unit tests)
        if not k in OPTS.__dict__ or k=="tech_name":
            OPTS.__dict__[k] = v
        if k == "openram_temp" and openram_temp is None:
            OPTS.set_temp_folder(v)
    
    if not os.path.isabs(OPTS.output_path):
        OPTS.output_path = os.path.join(os.getcwd(), OPTS.output_path)
    debug.info(1, "Output saved in " + OPTS.output_path)

    OPTS.is_unit_test=is_unit_test

    # If config didn't set output name, make a reasonable default.
    if (OPTS.output_name == ""):
        OPTS.output_name = "sram_{0}rw_{1}b_{2}w_{3}bank_{4}".format(OPTS.rw_ports,
                                                                     OPTS.word_size,
                                                                     OPTS.num_words,
                                                                     OPTS.num_banks,
                                                                     OPTS.tech_name)
        
    # Don't delete the output dir, it may have other files!
    # make the directory if it doesn't exist
    try:
        os.makedirs(OPTS.output_path, 0o750)
    except OSError as e:
        if e.errno == 17:  # errno.EEXIST
            os.chmod(OPTS.output_path, 0o750)
    except:
        debug.error("Unable to make output directory.",-1)
    
        
        
def end_openram():
    """ Clean up openram for a proper exit """
    cleanup_paths()
    

    
    
def cleanup_paths():
    """
    We should clean up the temp directory after execution.
    """
    if not OPTS.purge_temp:
        debug.info(1,"Preserving temp directory: {}".format(OPTS.openram_temp))
        return
    if os.path.exists(OPTS.openram_temp):
        shutil.rmtree(OPTS.openram_temp, ignore_errors=True)
            
def setup_paths():
    """ Set up the non-tech related paths. """
    debug.info(2,"Setting up paths...")

    global OPTS

    try:
        OPENRAM_HOME = os.path.abspath(os.environ.get("OPENRAM_HOME"))
    except:
        debug.error("$OPENRAM_HOME is not properly defined.",1)
    debug.check(os.path.isdir(OPENRAM_HOME),"$OPENRAM_HOME does not exist: {0}".format(OPENRAM_HOME))

    if hasattr(OPTS, "python_path"):
        python_path = OPTS.python_path
    else:
        python_path = []

    # Add all of the subdirs to the python path
    # These subdirs are modules and don't need to be added: characterizer, verify
    for subdir in ["tests", "modules", "modules/cam"] + python_path:
        full_path = os.path.abspath(os.path.join(OPENRAM_HOME, subdir))
        debug.check(os.path.isdir(full_path),
                    "{} does not exist:".format(full_path))
        sys.path.append("{0}".format(full_path)) 

    debug.info(1, "Temporary files saved in " + OPTS.openram_temp)

    cleanup_paths()

    # make the directory if it doesn't exist
    try:
        os.makedirs(OPTS.openram_temp, 0o750)
    except OSError as e:
        if e.errno == 17:  # errno.EEXIST
            os.chmod(OPTS.openram_temp, 0o750)


def is_exe(fpath):
    """ Return true if the given is an executable file that exists. """
    return os.path.exists(fpath) and not os.path.isdir(fpath) and os.access(fpath, os.X_OK)

def find_exe(check_exe):
    """ Check if the binary exists in any path dir and return the full path. """
    # Check if the preferred spice option exists in the path
    for path in os.environ["PATH"].split(os.pathsep):
        exe = os.path.join(path, check_exe)
        # if it is found, then break and use first version
        if is_exe(exe):
            return exe
    return None
        
# imports correct technology directories for testing
def import_tech():
    global OPTS

    debug.info(2,"Importing technology: " + OPTS.tech_name)

    # Set the tech to the config file we read in instead of the command line value.
    OPTS.tech_name = OPTS.tech_name
        
    # environment variable should point to the technology dir
    try:
        OPENRAM_TECH = os.path.abspath(os.environ.get("OPENRAM_TECH"))
    except:
        debug.error("$OPENRAM_TECH is not properly defined.",1)
    debug.check(os.path.isdir(OPENRAM_TECH),"$OPENRAM_TECH does not exist: {0}".format(OPENRAM_TECH))
    
    OPTS.openram_tech =os.path.join(OPENRAM_TECH, OPTS.tech_name)

    debug.info(1, "Technology path is " + OPTS.openram_tech)

    try:
        filename = "setup_openram_{0}".format(OPTS.tech_name)
        # we assume that the setup scripts (and tech dirs) are located at the
        # same level as the compielr itself, probably not a good idea though.
        path = os.path.join(os.environ.get("OPENRAM_TECH"), "setup_scripts")
        debug.check(os.path.isdir(path), "setup_scripts does not exist: {0}".format(path))
        sys.path.append(os.path.abspath(path))
        __import__(filename)
    except ImportError:
        debug.error("Nonexistent technology_setup_file: {0}.py".format(filename))
        sys.exit(1)

    import tech
    # Set some default options now based on the technology...
    if (OPTS.process_corners == ""):
        OPTS.process_corners = tech.spice["fet_models"].keys()
    if (OPTS.supply_voltages == ""):
        OPTS.supply_voltages = tech.spice["supply_voltages"]
    if (OPTS.temperatures == ""):
        OPTS.temperatures = tech.spice["temperatures"]

def initialize_classes():
    check_lvsdrc = OPTS.check_lvsdrc
    OPTS.check_lvsdrc = True
    if 'characterizer' not in sys.modules:
        import characterizer
    else:
        import characterizer
        reload(characterizer)

    if 'verify' not in sys.modules:
        import verify
    else:
        import verify
        reload(verify)
    # only bitcell is preloaded here because most unit tests only require loading bitcell to get it's dimensions
    reload(__import__(OPTS.bitcell))
    OPTS.check_lvsdrc = check_lvsdrc

def print_time(name, now_time, last_time=None):
    """ Print a statement about the time delta. """
    if last_time:
        time = round((now_time-last_time).total_seconds(),1)
    else:
        time = now_time
    debug.print_str("** {0}: {1} seconds".format(name,time))


def report_status():
    """ Check for valid arguments and report the info about the SRAM being generated """
    # Check if all arguments are integers for bits, size, banks
    if type(OPTS.word_size)!=int:
        debug.error("{0} is not an integer in config file.".format(OPTS.word_size))
    if type(OPTS.num_words)!=int:
        debug.error("{0} is not an integer in config file.".format(OPTS.sram_size))
    if type(OPTS.num_banks)!=int:
        debug.error("{0} is not an integer in config file.".format(OPTS.num_banks))

    if not OPTS.tech_name:
        debug.error("Tech name must be specified in config file.")

    debug.print_str("Technology: {0}".format(OPTS.tech_name))
    debug.print_str("Word size: {0}\nWords: {1}\nBanks: {2}".format(OPTS.word_size,
                                                          OPTS.num_words,
                                                          OPTS.num_banks))
    if not OPTS.check_lvsdrc:
        debug.print_str("DRC/LVS/PEX checking is disabled.")
    
