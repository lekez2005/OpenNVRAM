#!/bin/env python
import re
import os, sys
import builtins
import argparse

#-------------------------------------------------------------------------
# Command line processing
#-------------------------------------------------------------------------

class ArgumentParserWithCustomError(argparse.ArgumentParser):
  def error( self, msg = "" ):
    if ( msg ): print("\n ERROR: %s" % msg)
    print("")
    file = open( sys.argv[0] )
    for ( lineno, line ) in enumerate( file ):
      if ( line[0] != '#' ): sys.exit(msg != "")
      if ( (lineno == 2) or (lineno >= 4) ): print( line[1:].rstrip("\n") )

def parse_cmdline():
  p = ArgumentParserWithCustomError( add_help=False )

  # Standard command line arguments

  p.add_argument("-h", "--help",    action="store_true")

  # Additional commane line arguments for the simulator

  p.add_argument("-g", "--view", default="verilog", choices=["verilog", "db", "lef", "lib"] )

  p.add_argument( "-o", "--output", default = "."     ,
                                    action  = "store" )

  p.add_argument( "specs_filename" )

  opts = p.parse_args()
  if opts.help: p.error()
  return opts

#-------------------------------------------------------------------------
# Subshell stuff
#-------------------------------------------------------------------------

def subshell( cmd ):

  # get shell's enviornment
  env = {}
  env.update(os.environ)

  process        = subprocess.Popen( cmd                     ,
                                     stdin  = subprocess.PIPE,
                                     stdout = subprocess.PIPE,
                                     stderr = subprocess.PIPE,
                                     shell  = True           ,
                                     env    = env            )

  stdout, stderr = process.communicate()
  status         = process.returncode

  del process

  return stdout, stderr, status

#-------------------------------------------------------------------------
# Helper Functions
#-------------------------------------------------------------------------

def getArg(arg_n, val, prev = None):

    ret = prev
    arg = '--{}='.format(arg_n)

    if val.startswith(arg):
        ret = val[len(arg):]

    return ret

#-------------------------------------------------------------------------
# Main
#-------------------------------------------------------------------------

design = ''
uop    = ''
brief  = False
debug  = False

for arg in sys.argv:

    design = getArg('design', arg, design)
    uop    = getArg('uop'   , arg, uop   )
    brief  = True if arg == '--brief' else brief
    debug  = True if arg == '--debug' else debug
    debug  = True if arg == '-d'      else debug

if   design == 'bp-vram': design = 'compute'
elif design == 'bs-vram': design = 'serial'
else                    : exit(1)

design_dir = '{}_256_128'.format(design)
base_dir   = 'openram/bl_sram' # sim dir

directory  = '{}/{}/{}'.format(base_dir, design_dir, uop)

if debug:
    print(directory)

os.environ["temp_folder"] = directory

builtins.run_analysis = False

try:
    from analyze_simulation import *
except ImportError:
    from .analyze_simulation import *


num_trials = 10

#print(sim_data.get_bus_binary("v({})".format("Xsram.Xbank0.Xbitcell_array.Xbit_r0_c{}.Q"), 32, 0e-9))

total_energy = measure_energy([0, sim_data.time[-1]])

if brief:
    print('{:.3g}'.format(total_energy/num_trials*1e12))
else:
    print("Energy per operation = {:.3g} pJ".format(total_energy/num_trials*1e12))
