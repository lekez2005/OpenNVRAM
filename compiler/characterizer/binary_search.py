class BinarySearch:
    """Run binary search optimization based on objective function"""

    def __init__(self, objective_func, tolerance, *, start_value=None, lower_bound=None,
                 upper_bound=None, increment_factor=1.2, show_progress=True,
                 max_tries=10):
        self.start_value = start_value
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.increment_factor = increment_factor
        self.tolerance = tolerance
        self.objective_func = objective_func
        self.show_progress = show_progress
        self.max_tries = max_tries

    def optimize(self):
        if self.start_value is None:
            assert (self.lower_bound is not None and self.upper_bound is not None), \
                "Start value and End values must be specified if Start Value is None"
            current_value = 0.5 * (self.lower_bound + self.upper_bound)
        else:
            current_value = self.start_value

        upper_bound, lower_bound = self.upper_bound, self.lower_bound

        tries = 0

        while tries < self.max_tries:
            # check termination
            if upper_bound is not None and lower_bound is not None:
                if upper_bound - lower_bound < self.tolerance:
                    return upper_bound
            try:
                success, value_str = self.objective_func(current_value)
            except KeyboardInterrupt as ex:
                raise ex
            except:
                print(f"Process run error for {current_value}")
                success = False
                value_str = str(current_value)
            if self.show_progress:
                success_str = "Success" if success else "Fail   "
                print(f"{success_str} \t{value_str}", flush=True)

            if success:
                upper_bound = current_value
                if lower_bound is None:
                    current_value = (1 / self.increment_factor) * current_value
                else:
                    current_value = 0.5 * (lower_bound + upper_bound)
            else:
                lower_bound = current_value
                if upper_bound is None:
                    current_value = self.increment_factor * current_value
                else:
                    current_value = 0.5 * (lower_bound + upper_bound)

            tries += 1
        return None
