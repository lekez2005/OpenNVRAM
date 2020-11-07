from modules.push_rules.horizontal_predecode import horizontal_predecode


class predecode2x4_horizontal(horizontal_predecode):

    def get_nand_connections(self):
        return [["inbar[0]", "inbar[1]", "Z[0]", "vdd", "gnd"],
                ["in[0]", "inbar[1]", "Z[1]", "vdd", "gnd"],
                ["inbar[0]", "in[1]", "Z[2]", "vdd", "gnd"],
                ["in[0]", "in[1]", "Z[3]", "vdd", "gnd"]]

    def get_nand_input_line_combination(self):
        """ These are the decoder connections of the NAND gates to the A,B pins """
        combination = [["Abar[0]", "Abar[1]"],
                       ["A[0]", "Abar[1]"],
                       ["Abar[0]", "A[1]"],
                       ["A[0]", "A[1]"]]
        return combination
