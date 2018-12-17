from characterizer.sequential_delay import SequentialDelay
from globals import OPTS


class CustomSequentialDelay(SequentialDelay):

    def __init__(self, sram, spfile, corner, initialize=False):
        super(CustomSequentialDelay, self).__init__(sram, spfile, corner, initialize=initialize)
        self.col_zero_address = None
        self.col_one_address = None
        self.bank_two_address = None
        # set up for write
        self.web = 0
        self.oeb = 1
        self.csb = 0
        self.acc_en = 0
        self.acc_en_inv = 1
        self.seb = self.prev_seb = 1
        self.mwb = self.prev_mwb = 1
        self.bcastb = self.prev_bcastb = 1
        self.mask = self.prev_mask = [1] * OPTS.word_size
        for i in range(self.word_size):
            self.bus_sigs.append("mask[{}]".format(i))

    def generate_steps(self):

        # test read and write
        word_size = OPTS.word_size

        col_one_address = self.convert_address(self.col_one_address)
        col_zero_address = self.convert_address(self.col_zero_address)
        bank_two_address = self.convert_address(self.bank_two_address)



        # data is 11111...101010...

        data_prefix = [1]*int(word_size/4) + [0]*int(word_size/4)
        data_suffix = [1, 0]*int(word_size/4)

        col_zero_data = data_prefix + data_suffix
        col_one_data = data_prefix + [int(not(x)) for x in data_suffix]


        mask = [1]*word_size
        # bcast to all
        self.write_masked_data(col_zero_address, [0, 1, 1, 0]*int(word_size/4), mask, broadcast=True)

        # write to first column
        self.write_masked_data(col_zero_address, col_zero_data, mask)

        # write to second column
        self.write_masked_data(col_one_address, col_one_data, mask)
        self.write_masked_data(bank_two_address, col_one_data, mask)

        # read from first column
        self.read_data(col_zero_address)

        # read from second column
        self.read_data(col_one_address)

        # read from second bank
        self.read_data(bank_two_address)

        # wild card search to match just col_zero_address
        mask = [1]*word_size
        self.search_data(col_zero_data, mask)

        # wild card search to match all col_zero, col_one, bank_two
        self.search_data(data_prefix + [0]*int(word_size/2), [1]*int(word_size/2) + [0]*int(word_size/2))

        # write to matches
        self.multiwrite([0]*int(word_size), [1]*int(word_size/2) + [0]*int(word_size/2))

        # confirm matches were written including mask
        self.read_data(col_zero_address)  # should be 00000....10101...
        self.read_data(col_one_address)  # should be 00000...01010...

    def update_output(self):
        # write mask
        for i in range(self.word_size):
            key = "mask[{}]".format(i)
            self.write_pwl(key, self.prev_mask[i], self.mask[i])
        self.prev_mask = self.mask
        super(CustomSequentialDelay, self).update_output()


    def search_data(self, data, mask, comment=""):
        """data and mask are MSB first"""
        self.command_comments.append("* t = {} Search {}, Mask: {} {} \n".format(self.current_time, data,
                                                                                 mask, comment))
        self.data = list(reversed(data))
        self.mask = list(reversed(mask))
        self.acc_en = 0
        self.web = 1
        self.acc_en_inv = 1
        self.oeb = 1
        self.mwb = 1
        self.bcastb = 1
        self.seb = 0

        self.update_output()

    def multiwrite(self, data, mask, comment=""):
        """data and mask are MSB first"""
        self.command_comments.append("* t = {} Multi-write {}, Mask: {} {} \n".format(self.current_time, data,
                                                                                      mask, comment))
        self.data = list(reversed(self.convert_data(data)))
        self.mask = list(reversed(mask))
        self.acc_en = 0
        self.web = 1
        self.acc_en_inv = 1
        self.oeb = 1
        self.mwb = 0
        self.bcastb = 1
        self.seb = 1

        self.update_output()

    def write_masked_data(self, address_vec, data, mask_vec, broadcast=False, comment=""):
        """Write data to an address. Data can be integer or binary vector. Address is binary vector"""
        self.command_comments.append("* t = {} Write {} to {} {} \n".format(self.current_time, data,
                                                                            address_vec, comment))
        self.mask = list(reversed(mask_vec))
        self.address = list(reversed(address_vec))
        self.data = list(reversed(self.convert_data(data)))

        self.acc_en = self.web = 0
        self.acc_en_inv = 1
        self.oeb = 1
        self.mwb = 1
        if broadcast:
            self.bcastb = 0
        else:
            self.bcastb = 1
        self.seb = 1
        self.period = self.write_period
        self.update_output()

    def read_data(self, address_vec, comment=""):
        """Read from an address. Address is a binary vector"""
        # self.measure_write(address, data)
        self.command_comments.append("* t = {} Read {} {} \n".format(self.current_time, address_vec, comment))
        self.address = list(reversed(address_vec))

        self.acc_en = 1
        self.web = 1
        self.acc_en_inv = 0
        self.oeb = 0
        self.mwb = 1
        self.bcastb = 1
        self.seb = 1
        self.period = self.read_period
        self.update_output()

