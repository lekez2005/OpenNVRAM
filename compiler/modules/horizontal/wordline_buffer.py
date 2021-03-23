from base.contact import m2m3, m1m2
from base.design import METAL1, METAL2, METAL3
from base.hierarchy_layout import GDS_ROT_270
from base.vector import vector
from globals import OPTS
from modules.buffer_stage import BufferStage
from modules.push_rules.push_bitcell_array import push_bitcell_array
from modules.horizontal.wordline_inverter import wordline_inverter


class wordline_buffer(BufferStage):
    rotation_for_drc = GDS_ROT_270

    @classmethod
    def get_name(cls, buffer_stages, *args, **kwargs):
        name = "wordline_buffer_" + "_".join(['{:.3g}'.format(x) for x in buffer_stages])
        return name.replace(".", "__")

    def create_layout(self):
        super().create_layout()
        self.width = self.module_insts[-1].rx()
        self.add_boundary()

    def create_buffer_inv(self, size):
        index = self.buffer_stages.index(size)
        mirror = index % 2 == 1
        beta = OPTS.wordline_beta[index]
        inv = wordline_inverter(size=size, beta=beta, mirror=mirror)
        self.height = inv.height
        return inv

    def add_buffers(self):
        for i in range(self.total_instances):
            size = self.buffer_stages[i]
            inv = self.create_buffer_inv(size)
            self.add_mod(inv)
            self.buffer_invs.append(inv)

        extra_width = 2 * self.implant_enclose_poly - self.poly_to_field_poly
        right_x = self.buffer_invs[0].width - extra_width
        x_offsets = [0, right_x]
        connections = [("in", "out_inv"), ("out_inv", "out")]
        for i in range(2):
            inv_inst = self.add_inst("inv{}".format(i), self.buffer_invs[i],
                                     offset=vector(x_offsets[i], 0))
            self.module_insts.append(inv_inst)
            in_net, out_net = connections[i]
            self.connect_inst([in_net, out_net, "vdd", "gnd"])

    def route_out_pins(self):
        a_pin = self.module_insts[1].get_pin("A")
        z_pin = self.module_insts[0].get_pin("Z")
        self.add_rect(METAL1, offset=z_pin.lr(), width=a_pin.lx() - z_pin.rx())

        out_pin = self.module_insts[1].get_pin("Z")
        via_x = out_pin.rx()
        via_y = out_pin.cy() - 0.5 * m2m3.width
        self.add_contact(m1m2.layer_stack, offset=vector(via_x, via_y), rotate=90)
        self.add_contact(m2m3.layer_stack, offset=vector(via_x, via_y), rotate=90)
        fill_width = m2m3.height
        fill_width, fill_height = self.calculate_min_area_fill(fill_width, self.m2_width)
        self.add_rect(METAL2, offset=vector(via_x - fill_width, out_pin.cy() - 0.5 * fill_height),
                      width=fill_width, height=fill_height)

        wl_height = push_bitcell_array.bitcell.get_pin("wl").height()
        _, fill_width = self.calculate_min_area_fill(wl_height, m2m3.height, layer=METAL3)
        self.add_layout_pin("out", METAL3, offset=vector(out_pin.rx() - fill_width,
                                                         out_pin.cy() - 0.5 * wl_height),
                            width=fill_width, height=wl_height)
