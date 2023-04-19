#!env python3
"""
Sweep size of access device to guide selection of access device size
"""
import os

import numpy as np

from caravel_simulation_test import ReRamTestBase, SimulatorBase

dc_template = """
Xaccess tx_drain wl br gnd sky130_fd_pr__nfet_01v8 m=1 nf={nf} w={total_width:.4g} l=0.15
Rbe be tx_drain {contact_res}
Xmem te be sky130_fd_pr__reram_reram_cell Tfilament_0={Tfilament_0}
Rte te bl {contact_res}
Xwrite_driver {data_nets} vdd vdd bl br vdd vdd_write_bl vdd_write_br gnd {write_driver_name}

* Vwl wl 0 DC 0 PWL( 0 0 0.2n 0 0.21n {vdd_value} )
* .ic v(Xmem.state_out)={initial_thickness:.3g}
.probe i(Xaccess.msky130_fd_pr__nfet_01v8)
.op
"""

min_thickness = 3.3e-9
max_thickness = 4.9e-9
thickness_scale_factor = 1e7


def calculate_thickness(thick):
    if thick:
        percentage = 0.99
    else:
        percentage = 0.01
    thickness = (min_thickness + percentage * (max_thickness - min_thickness))
    return thickness


class AccessDeviceTest(SimulatorBase, ReRamTestBase):
    @classmethod
    def create_arg_parser(cls):
        parser = super(AccessDeviceTest, cls).create_arg_parser()
        parser.add_argument("--min_size", default=1, type=float)
        parser.add_argument("--max_size", default=20, type=float)
        parser.add_argument("--num_steps", default=20, type=int)
        parser.add_argument("--contact_res", default=100, type=float)
        parser.add_argument("--write_driver_size", default=20, type=float)
        parser.add_argument("--bl_vdd", default=2.4, type=float)
        parser.add_argument("--br_vdd", default=2.4, type=float)
        parser.add_argument("--thick", action="store_true")
        parser.add_argument("--save", action="store_true")

        return parser

    @classmethod
    def get_sim_directory(cls, cmd_line_opts):
        sim_dir = super().get_sim_directory(cmd_line_opts)
        sim_dir = os.path.join(os.path.dirname(sim_dir), "access_device")
        from globals import OPTS

        cls.sizes = np.linspace(cmd_line_opts.min_size, cmd_line_opts.max_size,
                                cmd_line_opts.num_steps)
        OPTS.vdd_write_bl = cmd_line_opts.bl_vdd
        OPTS.vdd_write_br = cmd_line_opts.br_vdd

        return sim_dir

    def run_spice_simulation(self, access_device_size, spice_template,
                             additional_spice, output_name,
                             data_value=True):

        from modules.reram.reram_spice_dut import ReramSpiceDut
        from globals import OPTS
        from characterizer.simulation.sim_reader import SimReader

        OPTS.write_driver_buffer_size = self.cmd_line_opts.write_driver_size
        write_driver = self.create_class_from_opts("write_driver")
        write_driver_file = os.path.join(OPTS.openram_temp, "write_driver.sp")
        write_driver.sp_write(write_driver_file)

        thickness = calculate_thickness(self.cmd_line_opts.thick)

        if data_value:
            data_nets = "vdd gnd"
        else:
            data_nets = "gnd vdd"

        # determine fingers and finger_width
        width = access_device_size * write_driver.min_tx_width
        number_fingers = int(min(4, max(1, np.floor(width / write_driver.min_tx_width))))

        with open(os.path.join(OPTS.openram_temp, "stim.sp"), "w") as f:
            stim = ReramSpiceDut(f, corner=self.corner)
            stim.write_include(write_driver_file)
            stim.write_supply()
            stim.generate_constant_voltages()
            additional_spice(stim)
            f.write(spice_template.format(nf=number_fingers, total_width=width,
                                          contact_res=self.cmd_line_opts.contact_res,
                                          vdd_value=stim.voltage,
                                          write_driver_name=write_driver.name,
                                          data_nets=data_nets,
                                          initial_thickness=thickness * thickness_scale_factor,
                                          Tfilament_0=thickness))
        stim.run_sim()

        sim_output_file = os.path.join(OPTS.openram_temp, output_name)
        reader = SimReader.get_reader(simulation_file=sim_output_file)
        return reader, width

    def test_write_time(self):
        from globals import OPTS
        rise_time = 0.1
        pulse_delay = 0.5
        sim_length = 100

        initial_thick = self.cmd_line_opts.thick
        results = []

        def additional_spice(stim):
            stim.sf.write(f"Vwl wl 0 PWL( 0 0 {pulse_delay}n 0"
                          f" {pulse_delay + rise_time}n {OPTS.vdd_wordline} )\n")

            stim.write_control(sim_length)

        for size in self.sizes:
            reader, width = self.run_spice_simulation(size, dc_template,
                                                      additional_spice, "tran.tran.tran",
                                                      data_value=not initial_thick)
            threshold = thickness_scale_factor * 0.5 * (min_thickness + max_thickness)
            threshold /= reader.vdd
            delay = reader.get_delay(signal_name1="wl", thresh1=0.5 * OPTS.vdd_wordline,
                                     signal_name2="Xmem.state_out", thresh2=threshold)
            results.append([size, width, delay * 1e9])
            print(results[-1])

        if self.cmd_line_opts.save:
            output_name = os.path.join(os.path.dirname(__file__), "access_data",
                                       "write_time.txt")
            np.savetxt(output_name, np.asarray(results), fmt="%.3g", delimiter=",")
        if OPTS.debug_level > 0:
            print(results)

    def _test_device_current(self):
        from globals import OPTS
        import matplotlib.pyplot as plt

        def additional_spice(stim):
            stim.generate_constant_voltages()
            stim.gen_constant("wl", OPTS.vdd_wordline)

        all_currents = []
        all_widths = []

        thickness = calculate_thickness(self.cmd_line_opts.thick)

        for size in self.sizes:
            reader, width = self.run_spice_simulation(size, dc_template,
                                                      additional_spice, "opBegin.dc")
            # thickness_data = reader.data.get_signal("Xmem.state_out")
            # temperature = reader.data.get_signal("Xmem.temperature_out")
            # print(reader.all_signal_names)
            current = reader.data.get_signal("i(Xaccess.msky130_fd_pr__nfet_01v8)")
            reader.close()

            print(f"size={size}, width={width:.3g}, current={current * 1e6:.5g}uA")

            all_currents.append(current * 1e6)
            all_widths.append(width)

        output_name = os.path.join(os.path.dirname(__file__), "access_data",
                                   f"thickness_{thickness * 1e9:.3g}")
        if not os.path.exists(os.path.dirname(output_name)):
            os.makedirs(os.path.dirname(output_name))
        if self.cmd_line_opts.save:
            np.savetxt(f"{output_name}.txt",
                       np.asarray([all_widths, all_currents]).transpose())
        plt.plot(all_widths, all_currents)
        plt.xlabel("Width (um)")
        plt.ylabel("Current (uA)")
        plt.grid()
        if self.cmd_line_opts.save:
            plt.savefig(f"{output_name}.png")
        plt.show()


if __name__ == "__main__":
    AccessDeviceTest.parse_options()
    AccessDeviceTest.run_tests(__name__)
