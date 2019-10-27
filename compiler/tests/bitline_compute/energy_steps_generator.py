from math import ceil

from globals import OPTS
from sim_steps_generator import SimStepsGenerator


class EnergyStepsGenerator(SimStepsGenerator):

    def generate_steps(self):
        # TODO addresses to use?
        a_address = self.sram.num_words - 1  # measure using topmost row
        b_address = 0
        c_address = int(self.sram.num_words/2)

        num_cols = self.num_cols
        word_size = self.word_size

        def select_cols(x):
            if len(x) >= num_cols:
                return x[:num_cols]
            else:
                repeats = ceil(num_cols/len(x))
                return (x*repeats)[:num_cols]

        data_one = select_cols([0]*word_size + [1, 0, 0, 1]*int(word_size/4))
        data_two = select_cols([0]*(word_size-1) + [1] + [1, 0, 1, 0]*int(word_size/4))
        data_three = select_cols([1] * word_size + [1, 1, 0, 0] * int(word_size / 4))

        mask_one = select_cols([1]*(2*word_size))
        mask_two = select_cols([1] * (2 * word_size))
        mask_three = select_cols([1]*word_size + [1, 1, 0, 0]*int(word_size/4))

        a_data = [data_three[i] if mask_three[i] else data_one[i] for i in range(num_cols)]
        b_data = data_two

        probe = self.probe_addresses([a_address, b_address, c_address])

        self.command_comments.append("* Period = {} \n".format(self.period))
        self.command_comments.append("* Duty Cycle = {} \n".format(self.duty_cycle))


        # TODO fill in energy sims depending on serial or parallel or baseline
        # New operations will need to be defined for the bit-serial case

        self.read_data(b_address, "Read B ({})".format(b_address))
        self.write_masked_data(a_address, data_one, mask_one, "Write A ({})".format(a_address))
        self.read_data(b_address, "Read B ({})".format(b_address))
        self.write_masked_data(b_address, data_two, mask_two, "Write B ({})".format(b_address))
        self.read_data(a_address, "Read A ({})".format(a_address))
        # set bank_sel to zero and measure leakage
        self.bank_sel = 0
        self.command_comments.append("*** t = {} {} \n".format(self.current_time, "Leakage"))
        self.write_pwl_from_key("bank_sel")
        self.current_time += 10*self.period

        self.saved_nodes = list(sorted(list(probe.saved_nodes) + list(self.dout_probes.values())
                                       + list(self.mask_probes.values())))

        self.saved_nodes.append(self.clk_buf_probe)

        self.saved_currents = probe.current_probes

