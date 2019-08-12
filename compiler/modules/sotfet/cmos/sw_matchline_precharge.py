from base import utils
from base.contact import m1m2
from base.vector import vector
from modules.sotfet.sf_matchline_precharge import sf_matchline_precharge
from tech import drc


class sw_matchline_precharge(sf_matchline_precharge):
    def add_ml_pin(self):

        rightmost_source = self.source_positions[-1]
        mid_y = self.active_y_offset + 0.5*self.ptx_width

        x_offset = rightmost_source - 0.5*self.m3_width

        if self.tx_mults == 1:
            self.add_contact_center(m1m2.layer_stack, offset=vector(rightmost_source, mid_y))
            # add m2 fill
            m2_fill_height = drc["minside_metal1_contact"]
            m2_fill_width = utils.ceil(self.minarea_metal1_contact / m2_fill_height)
            self.add_rect_center("metal2", offset=vector(rightmost_source, mid_y), width=m2_fill_width,
                                 height=m2_fill_height)

        self.add_layout_pin("ml", "metal1",
                            offset=vector(x_offset, mid_y-0.5*self.m1_width))

    def add_gnd_pin(self):
        self.add_layout_pin("gnd", "metal1", offset=vector(0, self.height-0.5*self.rail_height),
                            width=self.width, height=self.rail_height)
