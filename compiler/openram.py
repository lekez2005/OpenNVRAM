#!/usr/bin/env python3
"""
SRAM Compiler

The output files append the given suffixes to the output name:
a spice (.sp) file for circuit simulation
a GDS2 (.gds) file containing the layout
a LEF (.lef) file for preliminary P&R (real one should be from layout)
a Liberty (.lib) file for timing analysis/optimization

"""

import datetime
import sys

from globals import parse_args, print_time, USAGE, end_openram, print_banner, report_status, init_openram

OPTS, _ = parse_args()
assert OPTS.config_file is not None, "Config file must be specified"

# These depend on arguments, so don't load them until now.

init_openram(config_file=OPTS.config_file, is_unit_test=False)

# Only print banner here so it's not in unit tests
print_banner()

# Output info about this run
report_status()
# Start importing design modules after we have the config file

print("Output files are " + OPTS.output_name + ".(sp|gds|v|lib|lef)")

# Keep track of running stats
start_time = datetime.datetime.now()
print_time("Start", start_time)


if hasattr(OPTS, "create_sram"):
    s = OPTS.create_sram()
else:
    from base.design import design

    sram_class = design.import_mod_class_from_str(OPTS.sram_class)
    s = sram_class(word_size=OPTS.word_size,
                   num_words=OPTS.num_words,
                   num_banks=OPTS.num_banks,
                   name=OPTS.output_name)


# Output the files for the resulting SRAM
s.save_output()

# Delete temp files etc.
end_openram()
print_time("End", datetime.datetime.now(), start_time)
