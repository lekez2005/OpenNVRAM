import importlib.util
import os


module_dir = os.path.abspath(os.path.dirname(__file__))
testutils_path = os.path.abspath(os.path.join(module_dir, os.pardir, "testutils.py"))
spec = importlib.util.spec_from_file_location("testutils", testutils_path)
testutils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(testutils)

header = testutils.header


class CamTestBase(testutils.OpenRamTest):
    config_template = "config_cam_{}"



