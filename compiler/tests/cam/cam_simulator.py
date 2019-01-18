from cam_test_base import CamTestBase
from globals import OPTS


class CamSimulator(CamTestBase):

    def setUp(self):
        super(CamSimulator, self).setUp()

        from modules.cam import cam

        self.corner = (OPTS.process_corners[0], OPTS.supply_voltages[0], OPTS.temperatures[0])
        OPTS.word_size = 64
        OPTS.num_words = 64
        self.cam = cam.Cam(word_size=OPTS.word_size, num_words=OPTS.num_words, num_banks=1, name="cam",
                           words_per_row=OPTS.words_per_row)
        self.cam.sp_write(OPTS.spice_file)
        self.cam.gds_write(OPTS.gds_file)



    def run_commands(self, use_pex):
        from cam_probe import CamProbe
        from custom_sequential_delay import CustomSequentialDelay
        from custom_stimuli import CustomStimuli
        from tests.functional_test import FunctionalTest

        probe = CamProbe(self.cam, OPTS.pex_spice)

        func_test = FunctionalTest(self.cam, spice_name="spectre", use_pex=use_pex)

        col_zero_address = int(0)
        col_one_address = int(1)
        bank_two_address = int(OPTS.num_words/2)

        addresses = [col_zero_address, col_one_address, bank_two_address]
        func_test.probe = probe
        func_test.add_probes(addresses)
        for address in addresses:
            probe.probe_matchline(address)
            probe.probe_matchline(address+1)
            probe.probe_sense_amp(address)
            probe.probe_tagbits(address)
            probe.probe_tagbits(address+1)
        probe.add_misc_probes(None)
        func_test.addresses = addresses

        if use_pex:
            func_test.run_drc_lvs_pex()

        delay = CustomSequentialDelay(func_test.sram, func_test.spice_file, self.corner, initialize=False)
        delay.col_zero_address = col_zero_address
        delay.col_one_address = col_one_address
        delay.bank_two_address = bank_two_address

        delay.stim = CustomStimuli(None, self.corner)

        delay.slew = OPTS.slew_rate
        delay.load = OPTS.c_load
        delay.setup_time = OPTS.setup_time
        delay.period = OPTS.feasible_period

        # custom control signals
        delay.control_sigs = ["oeb", "web", "acc_en", "acc_en_inv", "csb", "seb", "mwb", "bcastb"]

        func_test.create_delay(self.corner, delay=delay)

        delay = func_test.delay

        delay.run_delay_simulation()

    # def test_schematic(self):
    #     use_pex = False
    #     self.run_commands(use_pex)

    def test_extracted(self):
        use_pex = True
        self.run_commands(use_pex)


CamTestBase.run_tests(__name__)
