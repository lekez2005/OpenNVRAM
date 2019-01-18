#!/usr/bin/env python3
"""
Test for correctness of decoder logic
"""

import re

import numpy as np

import debug
from cam_test_base import CamTestBase


class DecoderLogicTest(CamTestBase):

    def make_decoder(self, num_inputs):

        from modules.hierarchical_decoder import hierarchical_decoder
        decoder = hierarchical_decoder(num_inputs)
        return decoder

    def find_connection(self, row, decoder):
        """Return indices of connecions of a given row of a given row"""
        z_name = 'Z[{}]'.format(row)
        filter_lambda = lambda x: z_name in x and x.index(z_name) > 0
        z_connections = list(filter(filter_lambda, decoder.conns))
        if len(z_connections) == 1:
            return z_connections[0]
        else:
            raise KeyError("Invalid row {}".format(row))

    def get_row(self, inputs, groups):
        # get just the inputs
        inputs = inputs[:-3]
        pattern = re.compile('\[(\d+)\]')
        inputs = list(map(lambda x: int(pattern.search(x).groups()[0]), inputs))
        total = inputs[0]
        for i in range(1, len(inputs)):
            num_bits_lambda = lambda x: int(np.log2(len(x)))
            prev_bits = sum(map(num_bits_lambda, groups[:i]))
            offset = inputs[i] - groups[i][0]
            total += offset * 2**prev_bits
        return total


    def evaluate_n_inputs(self, num_inputs):
        from globals import OPTS
        OPTS.decoder_flops = True
        num_rows = 2**num_inputs
        debug.info(2, "Make {} row decoder".format(num_rows))
        decoder = self.make_decoder(num_rows)
        for i in range(num_rows):
            connections = self.find_connection(i, decoder)
            evaluated_row = self.get_row(connections, decoder.predec_groups)
            self.assertEqual(i, evaluated_row,
                             "Expected {} Got {} for decoder_{}".format(i, evaluated_row, num_rows))

    def test_4_input_decoder(self):
        self.evaluate_n_inputs(4)

    def test_5_input_decoder(self):
        self.evaluate_n_inputs(5)

    def test_6_input_decoder(self):
        self.evaluate_n_inputs(6)

    def test_7_input_decoder(self):
        self.evaluate_n_inputs(7)

    def test_8_input_decoder(self):
        self.evaluate_n_inputs(8)

    def test_9_input_decoder(self):
        self.evaluate_n_inputs(9)



CamTestBase.run_tests(__name__)
