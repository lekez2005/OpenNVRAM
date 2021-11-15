#!/usr/bin/env python3
"""
Estimate gate/drain capacitance for both NMOS and PMOS
"""
import os
import pathlib

from char_test_base import CharTestBase
from characterization_utils import TEN_FIFTY_THRESH, TEN_NINETY

ACTION_SINGLE = "single"
ACTION_SIZE_SWEEP = "size_sweep"
ACTION_PLOT_SIZE = "size_plot"
ACTION_PLOT_FINGERS = "fingers_plot"
NMOS = "nmos"
PMOS = "pmos"

GATE = "gate"
DRAIN = "drain"


class TxCapacitance(CharTestBase):
    buffer_stages = [1, 2]

    @classmethod
    def add_additional_options(cls):
        cls.parser.add_argument("-s", "--size", default=1,
                                type=float, help="Unit TX size")
        cls.parser.add_argument("--driver_size", default=4, type=float)
        cls.parser.add_argument("--tx_type", default=NMOS, choices=[NMOS, PMOS])
        cls.parser.add_argument("-f", "--num_fingers", default=4, type=int)
        cls.parser.add_argument("--terminal", default=GATE, choices=[DRAIN, GATE])
        cls.parser.add_argument("-m", "--method", default=TEN_FIFTY_THRESH,
                                choices=[TEN_NINETY, TEN_FIFTY_THRESH])

        cls.parser.add_argument("-a", "--action", default=ACTION_SIZE_SWEEP,
                                choices=[ACTION_SINGLE, ACTION_SIZE_SWEEP, ACTION_PLOT_SIZE,
                                         ACTION_PLOT_FINGERS])

    def test_single_sim(self):
        import debug
        if (not self.options.action == ACTION_SINGLE) or self.options.plot:
            return
        cap_val, cap_per_diff_micron, cap_per_tx_micron, cap_per_unit = \
            self.run_single_sim()
        debug.info(0, "Cap = {:.3g}fF".format(cap_val * 1e15))
        debug.info(0, "Cap per tx micron = {:.3g}fF".format(
            cap_per_tx_micron * 1e15))
        if self.options.terminal == DRAIN:
            debug.info(0, "Cap per diff micron = {:.3g}fF".format(cap_per_diff_micron * 1e15))
        debug.info(0, "Cap per unit = {:.3g}fF".format(cap_per_unit * 1e15))

    def test_size_sweep(self):
        from base.design import design

        if not self.options.action == ACTION_SIZE_SWEEP:
            return

        default_max_c = self.options.max_c
        default_min_c = self.options.min_c
        total_cap = default_max_c
        for tx_type in [NMOS, PMOS]:
            self.options.tx_type = tx_type
            print("\n{}".format(tx_type))
            for num_fingers in [1, 2, 3, 4, 5, 6, 10, 20, 40]:

                print("  fingers: {}".format(num_fingers))
                self.options.num_fingers = num_fingers

                for terminal in [DRAIN, GATE]:
                    print()

                    self.options.terminal = terminal

                    self.options.max_c = default_max_c
                    self.options.min_c = default_min_c
                    design.name_map.clear()

                    sizes = [1, 1.25, 1.5, 1.75, 2, 2.5, 3, 5, 10]
                    for i in range(len(sizes)):
                        size = sizes[i]
                        self.options.size = size

                        if i > 0:
                            self.options.max_c = (4 * total_cap)
                            self.options.min_c = 0.5 * total_cap

                        total_cap, _, cap_per_tx_micron, _ = self.run_single_sim()
                        print("      {}: \t size = {:.3g} \t C={:.3g}fF per micron".format(
                            terminal, size,
                            cap_per_tx_micron * 1e15))
                        file_suffixes = [("beta", self.options.beta)]
                        file_suffixes = []
                        size_suffixes = [("nf", num_fingers)]
                        pin_name = "d" if self.options.terminal == DRAIN else "g"
                        self.save_result(self.options.tx_type, pin_name, cap_per_tx_micron, size=size,
                                         file_suffixes=file_suffixes, size_suffixes=size_suffixes)

    def test_plot_by_size(self):
        if not self.options.action == ACTION_PLOT_SIZE:
            return
        image_file_suffix = "_size_beta{:.3g}".format(self.options.beta)

        self.run_plot(sweep_variable="size", image_file_suffix=image_file_suffix)

    def test_plot_by_fingers(self):
        if not self.options.action == ACTION_PLOT_FINGERS:
            return

        image_file_suffix = "_fingers_beta{:.3g}".format(self.options.beta)

        self.run_plot(sweep_variable="nf", image_file_suffix=image_file_suffix)

    def run_plot(self, sweep_variable, image_file_suffix: str):
        import matplotlib.pyplot as plt

        if not self.options.save_plot:
            image_file_suffix = None

        for i in range(2):
            tx_type = [NMOS, PMOS][i]
            sup_title = r"{} Caps $\beta$ = {:.3g}".format(tx_type.upper(),
                                                           self.options.beta)
            file_suffixes = [("beta", self.options.beta)]
            self.plot_results(tx_type, ["g", "d"], sweep_variable=sweep_variable,
                              file_suffixes=file_suffixes,
                              show_legend=True, scale_by_x=self.options.scale_by_x,
                              log_x=False, save_name_suffix=image_file_suffix,
                              sup_title=sup_title, show_plot=False)
            plt.show(block=[False, True][i])

    @staticmethod
    def create_mos_wrapper(options, beta_suffix=True):

        from base import contact
        from base.design import design
        from base.vector import vector
        from tech import info

        class MosWrapper(design):
            def __init__(self, mos: design):
                if beta_suffix:
                    suffix = "_beta{:.3g}".format(options.beta).replace(".", "_")
                else:
                    suffix = ""
                name = "wrap_" + mos.name + suffix
                super().__init__(name)
                inst = self.add_inst(mos.name, mos, offset=[0, 0])

                body_pin = "gnd" if options.tx_type == NMOS else "vdd"

                pin_list = ["D", "G", "S", body_pin]
                self.connect_inst(pin_list)
                self.add_mod(mos)
                self.add_pin_list(pin_list)
                for pin_name in ["D", "G", "S"]:
                    self.copy_layout_pin(inst, pin_name, pin_name)

                # add body contacts
                if options.tx_type == NMOS:
                    implant_name = "nimplant"
                    body_implant = "p"
                    well_type = "p"
                else:
                    implant_name = "pimplant"
                    body_implant = "n"
                    well_type = "n"

                lowest_implant = min(mos.get_layer_shapes(implant_name),
                                     key=lambda x: x.by())
                # conservatively large number of contacts for min area reasons
                body_contact = contact.contact(layer_stack=contact.well.layer_stack,
                                               dimensions=[6, 1],
                                               implant_type=body_implant,
                                               well_type=well_type)
                contact_implant = body_contact.get_layer_shapes(body_implant
                                                                + "implant")[0]
                y_offset = (lowest_implant.by() - contact_implant.height -
                            contact_implant.by())
                y_offset = min(y_offset, -(body_contact.height + 2 * self.m1_space))
                contact_offset = vector(0, y_offset)
                self.add_inst(body_contact.name, mod=body_contact,
                              offset=contact_offset)
                self.connect_inst([])

                # add body pin
                largest_m1 = max(body_contact.get_layer_shapes("metal1"),
                                 key=lambda x: x.width * x.height)
                pin_offset = contact_offset + largest_m1.offset
                self.add_layout_pin(body_pin, "metal1", offset=pin_offset,
                                    width=largest_m1.width,
                                    height=largest_m1.height)

                # connect nwells
                if info["has_{}well".format(well_type)]:
                    well_layer = "{}well".format(well_type)
                    tx_well = mos.get_layer_shapes(well_layer)[0]
                    contact_well = body_contact.get_layer_shapes(well_layer)[0]
                    rect_left = min(tx_well.lx(), contact_well.lx())
                    rect_right = max(tx_well.rx(), contact_well.rx())
                    rect_top = tx_well.by()
                    rect_bottom = contact_well.by() + contact_offset.y
                    self.add_rect(well_layer, offset=vector(rect_left, rect_bottom),
                                  width=rect_right - rect_left,
                                  height=rect_top - rect_bottom)
        return MosWrapper

    @staticmethod
    def create_pgate_wrapper(dut, options):
        if options.horizontal:
            pass
        else:
            pass
        name = "wrap_" + dut.name

    def run_single_sim(self):
        from globals import OPTS
        from pgates.ptx import ptx
        from tech import drc

        self.driver_size = self.options.driver_size

        beta_dir = "beta_{:.3g}".format(self.options.beta)
        OPTS.openram_temp = os.path.join(CharTestBase.temp_folder, beta_dir)
        if not os.path.exists(OPTS.openram_temp):
            pathlib.Path(OPTS.openram_temp).mkdir(parents=True, exist_ok=True)

        size = self.options.size

        tx_width = size * drc["minwidth_tx"]
        if self.options.tx_type == PMOS:
            tx_width = self.options.beta * tx_width

        mos_wrapper_class = self.create_mos_wrapper(self.options, beta_suffix=True)

        tx = mos_wrapper_class(ptx(width=tx_width, mults=self.options.num_fingers,
                                   tx_type=self.options.tx_type,
                                   connect_active=True, connect_poly=True))

        self.load_pex = self.run_pex_extraction(tx, tx.name,
                                                run_drc=self.run_drc_lvs,
                                                run_lvs=self.run_drc_lvs)

        self.dut_name = tx.name

        if self.options.tx_type == NMOS:
            source_gate_conn = "gnd"
        else:
            source_gate_conn = "vdd"

        if self.options.terminal == GATE:
            gate_terminal = "d"
            drain_terminal = "vdd" if self.options.tx_type == NMOS else "gnd"
        else:
            gate_terminal = source_gate_conn
            drain_terminal = "d"

        self.dut_instance = "X4 {drain_terminal} {gate_terminal} {source_gate_conn}" \
                            " {source_gate_conn}    {dut_name}          * real load \n" \
            .format(drain_terminal=drain_terminal, gate_terminal=gate_terminal,
                    source_gate_conn=source_gate_conn, dut_name=tx.name)

        self.run_optimization()

        total_cap = self.get_optimization_result()
        num_drains = 1 + int((self.options.num_fingers - 1) / 2)
        total_diffusion_height = num_drains * tx_width
        cap_per_diff_micron = total_cap / total_diffusion_height
        cap_per_tx_micron = total_cap / (self.options.num_fingers * tx_width)
        cap_per_unit = total_cap / (size * self.options.num_fingers)
        return total_cap, cap_per_diff_micron, cap_per_tx_micron, cap_per_unit


TxCapacitance.run_tests(__name__)
