#!/usr/bin/env python
from importlib import reload

from test_base import TestBase
import debug


class BlBankTest(TestBase):

    def test_bitline_compute_array(self):
        import tech
        tech.drc_exceptions["BlBank"] = tech.drc_exceptions["active_density"]
        from globals import OPTS

        if OPTS.baseline:
            return

        # self.sweep_all()
        self.sweep_all(cols=[64], rows=[64])

    def test_baseline_array(self):
        import tech
        from globals import OPTS

        if not OPTS.baseline:
            return

        tech.drc_exceptions["BlBaselineBank"] = tech.drc_exceptions["min_nwell"]

        self.sweep_all(cols=[64], rows=[64])
        #self.sweep_all()

    def sweep_all(self, rows=None, cols=None, default_row=64, default_col=64):
        from base import design
        from globals import OPTS
        from modules.bitline_compute.bl_bank import BlBank
        from modules.bitline_compute.baseline.bl_baseline_bank import BlBaselineBank
        if OPTS.baseline:
            bank_class = BlBaselineBank
        else:
            bank_class = BlBank

        OPTS.run_optimizations = False

        if rows is None:
            rows = [16, 32, 64, 128, 256]
        if cols is None:
            cols = [32, 64, 128, 256]

        try:
            col = default_col
            for row in rows:
                reload(design)
                debug.info(1, "Test {} single bank row = {} col = {}".format(
                    bank_class.__name__, row, col))
                a = bank_class(word_size=col, num_words=row, words_per_row=1, name="bank1")

                self.local_check(a)
            row = default_row
            for col in cols:
                if col == default_col:
                    continue
                reload(design)
                debug.info(1, "Test {} single bank row = {} col = {}".format(
                    bank_class.__name__, row, col))
                a = bank_class(word_size=col, num_words=row, words_per_row=1, name="bank1")
                self.local_check(a)
        except ZeroDivisionError as ex:
            debug.error("Failed {} for row = {} col = {}: {} ".format(
                bank_class.__name__, row, col, str(ex)), debug.ERROR_CODE)
            raise ex


TestBase.run_tests(__name__)
