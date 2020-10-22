#!/usr/bin/env python
from importlib import reload

from test_base import TestBase
import debug


class SramTest(TestBase):

    def test_baseline_array(self):
        from globals import OPTS

        if not OPTS.baseline:
            return

        # self.sweep_all(cols=None, rows=None, words_per_row=None, default_col=64, num_banks=2)
        self.sweep_all(cols=[], rows=[64], words_per_row=[1], default_col=256, num_banks=1)
        #self.sweep_all()

    def test_sotfet_array(self):
        from globals import OPTS
        if not OPTS.mram == "sotfet":
            return

        OPTS.run_optimizations = True

        self.sweep_all(cols=None, rows=None, words_per_row=None, default_col=64, num_banks=1)

    def sweep_all(self, rows=None, cols=None, words_per_row=None, default_row=64,
                  default_col=64, num_banks=1):
        from base import design
        from modules.shared_decoder.cmos_sram import CmosSram
        from modules.shared_decoder.sotfet.sotfet_mram import SotfetMram
        from globals import OPTS
        if OPTS.mram == "sotfet":
            sram_class = SotfetMram
        else:
            sram_class = CmosSram

        import tech
        tech.drc_exceptions["CmosSram"] = tech.drc_exceptions["active_density"]

        if rows is None:
            rows = [16, 32, 64, 128, 256]
        if cols is None:
            cols = [32, 64, 128, 256]

        try:
            col = default_col
            for row in rows:
                for words_per_row_ in SramTest.get_words_per_row(col, words_per_row):
                    reload(design)
                    self.create_and_test_sram(sram_class, row, col, words_per_row_, num_banks)
            row = default_row
            for col in cols:
                if col == default_col:
                    continue
                for words_per_row_ in SramTest.get_words_per_row(col, words_per_row):
                    reload(design)
                    self.create_and_test_sram(sram_class, row, col, words_per_row_, num_banks)
        except ZeroDivisionError as ex:
            debug.error("Failed {} for row = {} col = {}: {} ".format(
                sram_class.__name__, row, col, str(ex)), debug.ERROR_CODE)
            raise ex

    def create_and_test_sram(self, sram_class, num_rows, num_cols, words_per_row, num_banks):
        debug.info(1, "Test {} row = {} col = {} words_per_row = {} num_banks = {}".
                   format(sram_class.__name__, num_rows, num_cols, words_per_row, num_banks))
        word_size = int(num_cols / words_per_row)
        num_words = num_rows * words_per_row * num_banks
        a = sram_class(word_size=word_size, num_words=num_words, words_per_row=words_per_row,
                       num_banks=num_banks, name="sram1")

        self.local_check(a)


TestBase.run_tests(__name__)
