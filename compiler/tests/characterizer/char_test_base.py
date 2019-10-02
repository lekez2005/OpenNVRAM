import inspect
import os
import sys

sys.path.append('..')

import testutils


class CharTestBase(testutils.OpenRamTest):
    config_template = "config_20_{}"
    spice_template = "cin_template.sp"
    run_pex = True
    instantiate_dummy = False
    logic_buffers_height = 1.2
    driver_size = 8
    period = '800ps'
    max_iterations = 50
    use_mdl = False  # for some reason, mdl isn't as accurate, may need to investigate tolerances

    max_c = 100e-15
    min_c = 1e-15
    start_c = 0.5 * (max_c + min_c)

    def setUp(self):
        super().setUp()
        from globals import OPTS
        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])

        OPTS.check_lvsdrc = self.run_pex
        self.run_drc_lvs = self.run_pex

        OPTS.analytical_delay = False
        OPTS.spice_name = "spectre"

    @staticmethod
    def prefix(filename):
        from globals import OPTS
        return os.path.join(OPTS.openram_temp, filename)

    def run_pex_extraction(self, module, name_prefix):
        import verify

        spice_file = self.prefix("{}.sp".format(name_prefix))
        gds_file = self.prefix("{}.gds".format(name_prefix))
        pex_file = self.prefix("{}.pex.sp".format(name_prefix))
        if self.run_pex:
            module.sp_write(spice_file)
            module.gds_write(gds_file)

            errors = verify.run_pex(module.name, gds_file, spice_file, pex_file,
                                    run_drc_lvs=self.run_drc_lvs)
            if errors:
                raise AssertionError("PEX failed for {}".format(name_prefix))
        return pex_file

    @staticmethod
    def dummy_driver(args):
        template = """
Vin_dummy a_dummy gnd pulse {vdd_value} 0 0ps 20ps 20ps '0.5*PERIOD' 'PERIOD'
X1_dummy a_dummy b_dummy c_dummy vdd gnd        {in_buffer_name}    * set appropriate slope
X3_dummy c_dummy d_dummy d_bar_dummy vdd gnd    {driver_name}       * drive real load
X6_dummy c_dummy g_dummy g_bar_dummy vdd gnd    {driver_name}       * drive linear capacitor
cdelay_dummy g_dummy gnd 'Cload'                                          * linear capacitor
        """
        return template.format(**args)

    @staticmethod
    def generate_mdl(args):
        template = """
// more info at mdlref.pdf
alias measurement trans {{
    run tran( stop=2*{PERIOD}, autostop='yes)
    export real loadRise=cross(sig=V(d), dir='rise, n=1, thresh={half_vdd}) \\
        -  cross(sig=V(c), dir='fall, n=1, thresh={half_vdd})
    export real loadFall=cross(sig=V(d), dir='fall, n=1, thresh={half_vdd}) \\
        -  cross(sig=V(c), dir='rise, n=1, thresh={half_vdd})
    export real capRise=cross(sig=V(g), dir='rise, n=1, thresh={half_vdd}) \\
        -  cross(sig=V(c), dir='fall, n=1, thresh={half_vdd})
    export real capFall=cross(sig=V(g), dir='fall, n=1, thresh={half_vdd}) \\
        -  cross(sig=V(c), dir='rise, n=1, thresh={half_vdd})
}}

mvarsearch {{
    option {{
        method = 'lm  // can be 'newton
        accuracy = 1e-3 // convergence tolerance
        // deltax = 1e-5 // numerical difference % of design variables
        maxiter = {max_iterations} // limit to {max_iterations} iterations
    }}
    parameter {{
        {{ Cload, {start_c}, {min_c}, {max_c} }}
    }}
    exec {{
        run trans
    }}
    zero {{
        tmp1 = trans->loadRise - trans->capRise
        tmp2 = trans->loadFall - trans->capFall
    }}
}}
        """
        return template.format(**args)

    @staticmethod
    def generate_spice_optim(args):
        template = """
* More info at UltraSim_User.pdf
*----------------------------------------------------------------------
* Optimization setup
*----------------------------------------------------------------------
.measure errorR param='invR - capR' goal=0
.measure errorF param='invF - capF' goal=0
.param Cload=optrange({start_c}, {min_c}, {max_c})
.model optmod opt method=bisection itropt={max_iterations} relin=0.01
.measure Cl param = 'Cload'
*----------------------------------------------------------------------
* Stimulus
*----------------------------------------------------------------------
.tran 1ps '2*PERIOD' SWEEP OPTIMIZE = optrange
+ RESULTS=errorR,errorF MODEL=optmod
.measure invR
+ TRIG v(c) VAL='{half_vdd}' FALL=1
+ TARG v(d) VAL='{half_vdd}' RISE=1
.measure capR
+ TRIG v(c) VAL='{half_vdd}' FALL=1
+ TARG v(g) VAL='{half_vdd}' RISE=1
.measure invF
+ TRIG v(c) VAL='{half_vdd}' RISE=1
+ TARG v(d) VAL='{half_vdd}' FALL=1
.measure capF
+ TRIG v(c) VAL='{half_vdd}' RISE=1
+ TARG v(g) VAL='{half_vdd}' FALL=1
.end
        """
        return template.format(**args)

    def add_additional_includes(self, stim_file):
        pass

    def run_optimization(self):
        from modules.buffer_stage import BufferStage
        from characterizer.stimuli import stimuli
        from globals import OPTS
        import debug

        # in buffer
        in_buffer = BufferStage(buffer_stages=[1, 4], height=self.logic_buffers_height)
        in_pex = self.run_pex_extraction(in_buffer, "in_buffer")
        # driver
        driver = BufferStage(buffer_stages=[self.driver_size], height=self.logic_buffers_height)
        driver_pex = self.run_pex_extraction(driver, "driver")

        debug.info(2, "DUT name is {}".format(self.dut_name))
        debug.info(2, "Running simulation for corner {}".format(self.corner))

        spice_template = open(self.spice_template, 'r').read()
        vdd_value = self.corner[1]

        args = {
            "vdd_value": vdd_value,
            "PERIOD": self.period,
            "in_buffer_name": in_buffer.name,
            "driver_name": driver.name,
            "half_vdd": 0.5 * vdd_value,
            "start_c": self.start_c,
            "min_c": self.min_c,
            "max_c": self.max_c,
            "dut_instance": self.dut_instance,
            "max_iterations": self.max_iterations

        }

        if self.instantiate_dummy:
            dummy_str = self.dummy_driver(args)
        else:
            dummy_str = ""

        args["dummy_inst"] = dummy_str

        spice_content = spice_template.format(**args)
        self.stim_file_name = self.prefix("stim.sp")

        stim = None

        with open(self.stim_file_name, "w") as stim_file:
            stim_file.write("simulator lang=spice \n")
            stim = stimuli(stim_file, corner=self.corner)
            stim.write_include(in_pex)
            stim_file.write(".include \"{0}\" \n".format(self.load_pex))
            stim_file.write(".include \"{0}\" \n".format(driver_pex))

            self.add_additional_includes(stim_file)

            stim_file.write(spice_content)

            stim_file.write("\nsimulator lang=spectre\n")
            stim_file.write("simulatorOptions options temp={0} preservenode=all dc_pivot_check=yes" 
                            " \n".format(self.corner[2]))

            stim_file.write("saveOptions options save=lvlpub nestlvl=1 pwr=total \n")
            stim_file.write("simulator lang=spice \n")

            if self.use_mdl:
                stim_file.write(".PARAM Cload=1f\n")
                OPTS.spectre_options = " =mdlcontrol optimize.mdl "

                self.mdl_file = self.prefix("optimize.mdl")
                with open(self.mdl_file, "w") as mdl_file:
                    mdl_file.write(self.generate_mdl(args))
            else:
                stim_file.write(self.generate_spice_optim(args))

        stim.run_sim()


if '-skip_pex' in sys.argv:
    CharTestBase.run_pex = False
    sys.argv.remove('-skip_pex')

if '-use_mdl' in sys.argv:
    CharTestBase.use_mdl = True
    sys.argv.remove('-use_mdl')

# http://code.activestate.com/recipes/579018-python-determine-name-and-directory-of-the-top-lev/
for teil in inspect.stack():
        # skip system calls
        if teil[1].startswith("<"):
            continue
        if teil[1].upper().startswith(sys.exec_prefix.upper()):
            continue
        trc = teil[1]

test_name = os.path.basename(trc)[:-3]
openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "characterization", test_name)
openram_temp = os.path.join(os.environ["SCRATCH"], "openram", "characterization", "measure_resistance2")
CharTestBase.temp_folder = openram_temp
