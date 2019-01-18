import debug
from base import design
from base import unique_meta
from base import utils
from globals import OPTS
from tech import GDS, layer


class body_tap(design.design, metaclass=unique_meta.Unique):
    """
    A single bit cell (6T, 8T, etc.)  This module implements the
    single memory cell used in the design. It is a hand-made cell, so
    the layout and netlist should be available in the technology
    library.
    """

    name = OPTS.body_tap

    (width, height) = utils.get_libcell_size(name, GDS["unit"], layer["boundary"])

    def __init__(self):
        design.design.__init__(self, self.name)
        debug.info(2, "Create body tap")

        self.width = body_tap.width
        self.height = body_tap.height

    @classmethod
    def get_name(cls):
        return cls.name
