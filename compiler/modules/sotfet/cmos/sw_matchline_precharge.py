from base.vector import vector
from modules.sotfet.sf_matchline_precharge import sf_matchline_precharge


class sw_matchline_precharge(sf_matchline_precharge):

    def add_gnd_pin(self):
        self.add_layout_pin("gnd", "metal1", offset=vector(0, self.height-0.5*self.rail_height),
                            width=self.width, height=self.rail_height)
