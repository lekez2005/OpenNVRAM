import os

from test_base import TestBase


class AndInvTest(TestBase):
    def test_and_inv(self):
        from modules.bitline_compute.and_inv import and_inv
        from globals import OPTS

        a = and_inv()
        tempspice = os.path.join(OPTS.openram_temp, "temp.sp")
        a.sp_write(tempspice)


TestBase.run_tests(__name__)