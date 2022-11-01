import os
import subprocess
import time

from globals import OPTS


def create_pre_exec_fcn():
    pre_exec_fcn = None
    try:
        import psutil
        nice_value = os.getenv("OPENRAM_SUBPROCESS_NICE", 15)
        if nice_value:
            def pre_exec_fcn():
                pid = os.getpid()
                ps = psutil.Process(pid)
                ps.nice(int(nice_value))
    except ImportError:
        pass
    return pre_exec_fcn


def run_command_(command, stdout=None, stderr=None, line_processor=None, cwd=None, shell=True):
    if stdout is None:
        stdout = subprocess.PIPE
    if stderr is None:
        stderr = subprocess.STDOUT

    if line_processor is None:
        def line_processor(line_):
            print(line_, end="")
    if cwd is None:
        cwd = OPTS.openram_temp

    pre_exec_fcn = create_pre_exec_fcn()

    process = subprocess.Popen(command, stdout=stdout, stderr=stderr, shell=shell,
                               cwd=cwd, preexec_fn=pre_exec_fcn)
    while process.stdout:
        line = process.stdout.readline().decode()
        if not line:
            process.stdout.close()
            break
        else:
            line_processor(line)

    if process is not None:
        while process.poll() is None:
            # Process hasn't exited yet, let's wait some
            time.sleep(0.5)
        return process.returncode
    else:
        return -1


def run_command(command, stdout_file, stderror_file, verbose_level=1, cwd=None):
    verbose = OPTS.debug_level >= verbose_level
    if verbose:
        print(command)
    import debug

    def line_processor(line):
        if verbose:
            debug.print_str(line.rstrip())
        stdout_f.write(line)

    with open(stdout_file, "w") as stdout_f, open(stderror_file, "w") as stderr_f:
        stdout = subprocess.PIPE if verbose else stdout_f
        stderr = subprocess.STDOUT if verbose else stderr_f
        return run_command_(command, stdout, stderr, line_processor, cwd=cwd)
