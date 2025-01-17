#!/usr/bin/env python3
"Run a regression test the library cells for DRC"

import os
import sys
import unittest

from tests.testutils import header

sys.path.append(os.path.join(sys.path[0],"../.."))
sys.path.append(os.path.join(sys.path[0],".."))
import globals
import debug
from verify import calibre

OPTS = globals.OPTS

class expand_region_test(unittest.TestCase):
    """
    Test an infeasible route followed by a feasible route with an expanded region.
    """

    def runTest(self):
        globals.init_openram("config_{0}".format(OPTS.tech_name))

        from base import design
        import router

        class gdscell(design.design):
            """
            A generic GDS design that we can route on.
            """
            def __init__(self, name):
                #design.design.__init__(self, name)
                debug.info(2, "Create {0} object".format(name))
                self.name = name
                self.gds_file = "{0}/{1}.gds".format(os.path.dirname(os.path.realpath(__file__)),name)
                self.sp_file = "{0}/{1}.sp".format(os.path.dirname(os.path.realpath(__file__)),name)
                design.hierarchy_layout.layout.__init__(self, name)
                design.hierarchy_spice.spice.__init__(self, name)
            
        class routing(design.design,unittest.TestCase):
            """
            A generic GDS design that we can route on.
            """
            def __init__(self, name):
                design.design.__init__(self, name)
                debug.info(2, "Create {0} object".format(name))

                cell = gdscell(name)
                self.add_inst(name=name,
                              mod=cell,
                              offset=[0,0])
                self.connect_inst([])
                
                self.gdsname = "{0}/{1}.gds".format(os.path.dirname(os.path.realpath(__file__)),name)
                r=router.router(self.gdsname)
                layer_stack =("metal1","via1","metal2")
                # This should be infeasible because it is blocked without a detour. 
                self.assertFalse(r.route(self,layer_stack,src="A",dest="B",detour_scale=1))
                # This should be feasible because we allow it to detour
                self.assertTrue(r.route(self,layer_stack,src="A",dest="B",detour_scale=3))

        r = routing("08_expand_region_test_{0}".format(OPTS.tech_name))
        self.local_check(r)
        
        # fails if there are any DRC errors on any cells
        globals.end_openram()


    def local_check(self, r):
        tempgds = OPTS.openram_temp + "temp.gds"
        r.gds_write(tempgds)
        self.assertFalse(calibre.run_drc(r.name, tempgds))
        os.remove(tempgds)


                             


# instantiate a copy of the class to actually run the test
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main()
