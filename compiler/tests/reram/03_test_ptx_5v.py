#!env python3

from reram_test_base import ReRamTestBase


class Ptx5VTest(ReRamTestBase):
    def test_min_size_nmos(self):
        from devices_5v import ptx_5v
        tx = ptx_5v(width=1, tx_type="nmos", mults=1, contact_poly=True)
        self.local_drc_check(tx)

    def test_min_size_pmos(self):
        from devices_5v import ptx_5v
        tx = ptx_5v(width=1, tx_type="pmos", mults=1, contact_poly=True)
        self.local_drc_check(tx)

    def test_multiple_fingers(self):
        from devices_5v import ptx_5v
        tx = ptx_5v(width=1, tx_type="nmos", mults=3, contact_poly=True,
                    connect_active=True)
        self.local_drc_check(tx)


Ptx5VTest.run_tests(__name__)
