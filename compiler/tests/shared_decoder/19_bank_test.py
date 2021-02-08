#!/usr/bin/env python
from importlib import reload

from test_base import TestBase
import debug


class BankTest(TestBase):

    def test_sotfet_mram_array(self):
        from globals import OPTS
        import tech

        if not OPTS.mram == "sotfet":
            return

        tech.drc_exceptions["SotfetMramBank"] = (tech.drc_exceptions["min_nwell"] +
                                                 tech.drc_exceptions["latchup"])

        # self.sweep_all()
        self.sweep_all(cols=[64], rows=[64], words_per_row=2)

    def test_baseline_array(self):

        from globals import OPTS

        if not OPTS.baseline:
            return

        # self.sweep_all(cols=[], rows=[64], words_per_row=1, default_col=256)
        self.sweep_all()

    @staticmethod
    def get_bank_class():
        from globals import OPTS
        from modules.shared_decoder.cmos_bank import CmosBank
        from modules.shared_decoder.sotfet.sotfet_mram_bank import SotfetMramBank
        if OPTS.baseline:
            bank_class = CmosBank
        else:
            bank_class = SotfetMramBank
        return bank_class, {}

    def sweep_all(self, rows=None, cols=None, words_per_row=None, default_row=64, default_col=64):
        import tech
        from base import design
        from globals import OPTS

        bank_class, kwargs = self.get_bank_class()

        # tech.drc_exceptions[bank_class.__name__] = tech.drc_exceptions["min_nwell"] + tech.drc_exceptions["latchup"]
        tech.drc_exceptions[bank_class.__name__] = tech.drc_exceptions.get("latchup", [])

        OPTS.run_optimizations = False

        if rows is None:
            rows = [16, 32, 64, 128, 256]
        if cols is None:
            cols = [32, 64, 128, 256]

        try:
            col = default_col
            for row in rows:
                for words_per_row_ in BankTest.get_words_per_row(col, words_per_row):
                    reload(design)
                    debug.info(1, "Test {} single bank row = {} col = {} words_per_row = {}".
                               format(bank_class.__name__, row, col, words_per_row_))
                    word_size = int(col / words_per_row_)
                    num_words = row * words_per_row_
                    a = bank_class(word_size=word_size, num_words=num_words, words_per_row=words_per_row_,
                                   name="bank1", **kwargs)

                    self.local_check(a)
            row = default_row
            for col in cols:
                if col == default_col:
                    continue
                for words_per_row_ in BankTest.get_words_per_row(col, words_per_row):
                    reload(design)
                    debug.info(1, "Test {} single bank row = {} col = {} words_per_row = {}".
                               format(bank_class.__name__, row, col, words_per_row_))
                    word_size = int(col / words_per_row_)
                    num_words = row * words_per_row_
                    a = bank_class(word_size=word_size, num_words=num_words, words_per_row=words_per_row_,
                                   name="bank1")
                    self.local_check(a)
        except Exception as ex:
            debug.error("Failed {} for row = {} col = {}: {} ".format(
                bank_class.__name__, row, col, str(ex)), 0)
            raise ex

    def test_chip_sel(self):
        """Test for chip sel: Two independent banks"""
        from globals import OPTS
        bank_class, kwargs = self.get_bank_class()
        OPTS.route_control_signals_left = True
        OPTS.independent_banks = True
        OPTS.num_banks = 2
        a = bank_class(word_size=64, num_words=64, words_per_row=1,
                       name="bank1", **kwargs)
        self.local_check(a)

    def test_left_control_signals_rails(self):
        """Control rails routed to the left of the peripherals arrays"""
        from globals import OPTS
        bank_class, kwargs = self.get_bank_class()
        OPTS.route_control_signals_left = True
        OPTS.num_banks = 1

        a = bank_class(word_size=64, num_words=64, words_per_row=1,
                       name="bank1", **kwargs)

        self.local_check(a)

    def test_intra_array_control_signals_rails(self):
        """Test for control rails within peripherals arrays but not centralized
            (closest to driver pin)"""
        from globals import OPTS
        bank_class, kwargs = self.get_bank_class()
        OPTS.route_control_signals_left = False
        OPTS.num_banks = 1
        OPTS.centralize_control_signals = False
        a = bank_class(word_size=64, num_words=64, words_per_row=1,
                       name="bank1", **kwargs)
        self.local_check(a)

    def test_intra_array_centralize_control_signals_rails(self):
        """Test for when control rails are centralized in between bitcell array"""
        from globals import OPTS
        bank_class, kwargs = self.get_bank_class()
        OPTS.route_control_signals_left = False
        OPTS.num_banks = 1
        OPTS.centralize_control_signals = True
        a = bank_class(word_size=64, num_words=64, words_per_row=1,
                       name="bank1", **kwargs)
        self.local_check(a)

    def test_intra_array_wide_control_buffers(self):
        """Test for when control buffers width is greater than bitcell array width"""
        from globals import OPTS
        bank_class, kwargs = self.get_bank_class()
        OPTS.route_control_signals_left = False
        OPTS.num_banks = 1
        OPTS.control_buffers_num_rows = 1
        OPTS.centralize_control_signals = False
        a = bank_class(word_size=16, num_words=64, words_per_row=1,
                       name="bank1", **kwargs)
        self.assertTrue(a.control_buffers.width > a.bitcell_array.width,
                        "Adjust word size such that control buffers is wider than bitcell array")
        self.local_check(a)


TestBase.run_tests(__name__)
