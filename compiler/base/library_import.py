import debug
from base import design
from base import utils
from tech import GDS, layer


def library_import(cls):
    """
    Class annotation to import gds and sp files from  tech library by specifying cls.lib_name and cls.pin_names
    The order of cls.pin_names should match that in the sp file
    Instantiations of the class should use cls.pin_names for pin assignment
    :param cls:
    :return:
    """
    class GdsLibImport(cls):
        (width, height) = utils.get_libcell_size(cls.lib_name, GDS["unit"], layer["boundary"])
        pin_map = utils.get_libcell_pins(cls.pin_names, cls.lib_name, GDS["unit"], layer["boundary"])

        def __init__(self):
            design.design.__init__(self, cls.lib_name)
            debug.info(2, "Create {}".format(cls.lib_name))
            self.width = GdsLibImport.width
            self.height = GdsLibImport.height
            self.pin_map = GdsLibImport.pin_map
    return GdsLibImport
