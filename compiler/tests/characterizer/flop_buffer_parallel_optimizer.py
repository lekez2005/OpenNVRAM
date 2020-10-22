import os
import re
import sys
import traceback


from char_test_base import parallel_sim
import numpy as np

MAX_PARALLEL_JOBS = 10


max_size = 30
min_size = 1

results = os.path.join("flop_buffer", "double_stage_2.csv")

num_sims = 20

sizes = np.linspace(min_size, max_size, num_sims)
sizes = [int(x*100)/100 for x in sizes]
print(sizes)

output_dirs = []


def generate_command(stages_):
    return [sys.executable, "flop_buffer_optimizer.py", "#".join(map(str, stages_))]


def get_temp_dir(stages_):
    print(stages_)
    sim_name = "buffer_" + "_".join(["{:.3g}".format(x) for x in stages_])
    openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "characterization", sim_name)
    return openram_temp


def generate_iterations_single():
    for size in sizes:
        stages = [size]
        output_dirs.append((([0, size]), get_temp_dir(stages)))
        yield generate_command(stages)


def generate_iterations_double():
    for size_1 in range(1, 6):
        for size_2 in sizes:
            stages = [size_1, size_2]
            output_dirs.append(((stages), get_temp_dir(stages)))
            yield generate_command(stages)


parallel_sim(generate_iterations_double(), max_jobs=MAX_PARALLEL_JOBS)

with open(results, "w") as results_f:
    try:
        for stages, output_dir in output_dirs:
            meas_file = os.path.join(output_dir, "stim.measure")
            with open(meas_file, 'r') as f:
                for line in f:
                    if line.startswith("dout_delay"):
                        matches = re.match(r"dout_delay\s+=\s+(.+)", line)
                        output_delay = float(matches.group(1))
                        to_write = "{}, {}, {}\n".format(stages[0], stages[1], output_delay)
                        print(to_write)
                        results_f.write(to_write)
                        break
    except Exception:
        traceback.print_exc()
