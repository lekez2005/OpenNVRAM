from base import contact
from base import utils
from base.vector import vector
from globals import OPTS
from cam_block import cam_block
from wwl_driver_array import WwlDriverArray


class cam_block_wwl(cam_block):
    """
    Generate a CAM block whose bitcells include a write wordline.
    Augments cam_block with WWL driver
    """


    def create_modules(self):
        super(cam_block_wwl, self).create_modules()
        self.wwl_driver_array = WwlDriverArray(rows=self.num_rows, buffer_stages=OPTS.wwl_buffer_stages,
                                               no_cols=self.num_cols)
        self.add_mod(self.wwl_driver_array)

    def route_layout(self):
        super(cam_block_wwl, self).route_layout()
        self.route_wwl_driver()


    def add_bitcell_array(self):
        """ Adding Bitcell Array """

        self.bitcell_array_inst = self.add_inst(name="bitcell_array",
                                              mod=self.bitcell_array,
                                              offset=vector(0, 0))
        temp = []
        for i in range(self.num_cols):
            temp.append("bl[{0}]".format(i))
            temp.append("br[{0}]".format(i))
            temp.append("sl[{0}]".format(i))
            temp.append("slb[{0}]".format(i))
        for j in range(self.num_rows):
            temp.append("wl[{0}]".format(j))
            temp.append("wwl[{0}]".format(j))
            temp.append("ml[{0}]".format(j))
        temp.extend(["vdd", "gnd"])
        self.connect_inst(temp)

    def add_wwl_driver_array(self):
        x_offset = -self.overall_central_bus_width - self.wwl_driver_array.width - self.wide_m1_space - self.m2_width
        self.wwl_driver_array_inst = self.add_inst("wwl_driver_array", mod=self.wwl_driver_array,
                                                   offset=vector(x_offset, 0))
        temp = []
        for i in range(self.num_rows):
            temp.append("wl_in[{0}]".format(i))
        for i in range(self.num_rows):
            temp.append("wwl[{0}]".format(i))
        temp.append(self.prefix + "w_en")
        temp.append("vdd")
        temp.append("gnd")
        self.connect_inst(temp)

    def add_wordline_driver(self):
        self.add_wwl_driver_array()
        self.wwl_wordline_space = self.poly_width + self.poly_space
        self.wordline_x_offset = self.wwl_driver_array_inst.lx() - self.wordline_driver.width - self.wwl_wordline_space

        super(cam_block, self).add_wordline_driver()



    def route_wwl_driver(self):
        self.fill_wwl_implant_space()
        for row in range(self.num_rows):
            # connect input
            wl_in_pin = self.wordline_driver_inst.get_pin("in[{}]".format(row))
            wwl_in_pin = self.wwl_driver_array_inst.get_pin("in[{}]".format(row))
            self.add_contact(contact.m2m3.layer_stack,
                             offset=wl_in_pin.rc() - vector(0.5*contact.m2m3.second_layer_width,
                                                            0.5*contact.m2m3.second_layer_height))
            self.add_path("metal3", [wl_in_pin.rc(),
                                     vector(wwl_in_pin.lx() + 0.5*self.m3_width, wl_in_pin.cy()),
                                     vector(wwl_in_pin.lx() + 0.5*self.m3_width, wwl_in_pin.cy())])
            # connect output
            wwl_out_pin = self.wwl_driver_array_inst.get_pin("wwl[{}]".format(row))
            bitcell_in_pin = self.bitcell_array_inst.get_pin("wwl[{}]".format(row))
            self.add_path("metal1", [wwl_out_pin.center(),
                                     vector(wwl_out_pin.cx(), bitcell_in_pin.cy()),
                                     vector(bitcell_in_pin.lx() + 0.5*self.m1_width, bitcell_in_pin.cy())])

            # route w_en input
            gate_pin = self.bank_gate_inst.get_pin(self.prefix + "w_en")
            driver_pin = self.wwl_driver_array_inst.get_pin("en")
            self.add_contact(contact.m1m2.layer_stack, offset=vector(gate_pin.ll()), rotate=90)
            offset = vector(driver_pin.lx(), gate_pin.by())
            self.add_rect("metal1", offset=offset, width=gate_pin.lx() - driver_pin.lx())
            self.add_rect("metal2", offset=offset, height=driver_pin.by() - gate_pin.by())
            self.add_contact(contact.m1m2.layer_stack, offset=offset)

    def fill_wwl_implant_space(self):
        driver_mod = self.wwl_driver_array.driver_mod
        nand = driver_mod.logic_mod

        for row in range(self.num_rows):
            for layer in ["pimplant", "nimplant"]:
                implant_rect = max(nand.get_layer_shapes(layer), key=lambda x: x.height)
                ll, ur = utils.get_pin_rect(implant_rect, [self.wwl_driver_array_inst,
                                                         self.wwl_driver_array.module_insts[row]])
                self.add_rect(layer, offset=ll - vector(self.wwl_wordline_space, 0), width=self.wwl_wordline_space,
                              height=ur[1]-ll[1])

    def route_wordline_out(self):
        for row in range(self.num_rows):
            output_inst = self.wordline_driver.output_insts[row]
            ll, ur = utils.get_pin_rect(output_inst.get_pin("Z"), [self.wordline_driver_inst])

            bitcell_wl_pin = self.bitcell_array_inst.get_pin("wl[{}]".format(row))
            self.add_contact(contact.m2m3.layer_stack, offset=vector(ur[0], ur[1] - 0.5*self.m3_width), rotate=90)
            mid_x = self.wwl_driver_array_inst.rx() + self.m2_space
            self.add_path("metal3", [ur, vector(mid_x, ur[1])])
            offset = vector(mid_x, ur[1] - contact.m2m3.second_layer_height + 0.5 * self.m3_width)
            self.add_contact(contact.m2m3.layer_stack, offset=offset)
            self.add_contact(contact.m1m2.layer_stack, offset=offset)

            fill_width = 1.5*self.m2_width
            fill_height = utils.ceil(self.minarea_metal1_minwidth/fill_width)

            if fill_height > self.m2_width:
                self.add_rect("metal2", offset=vector(mid_x - 0.5*(fill_width - self.m2_width), ur[1] - 0.5*fill_height),
                              width=fill_width, height=fill_height)

            self.add_path("metal1", [vector(mid_x + 0.5*contact.m1m2.second_layer_width, ur[1]),
                                     vector(mid_x + 0.5*contact.m1m2.second_layer_width, bitcell_wl_pin.cy()),
                                     bitcell_wl_pin.lc()])

