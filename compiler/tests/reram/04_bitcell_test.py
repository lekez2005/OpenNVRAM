from reram_test_base import ReRamTestBase


class BitcellTest(ReRamTestBase):
    def test_bitcell(self):
        cell = self.create_class_from_opts("bitcell")
        self.local_check(cell)

    def test_bitcell_tap(self):
        cell = self.create_class_from_opts("body_tap")
        self.local_drc_check(cell)


BitcellTest.run_tests(__name__)
