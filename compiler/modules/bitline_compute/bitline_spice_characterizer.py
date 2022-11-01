import random
from math import ceil

from characterizer import SpiceCharacterizer, debug
from globals import OPTS
from modules.bitline_compute.bl_probe import BlProbe
from modules.bitline_compute.spice_dut import SpiceDut


class BitlineSpiceCharacterizer(SpiceCharacterizer):
    ramp_time = period = 0
    write_period = read_period = 0
    read_duty_cycle = write_duty_cycle = 0.5
    saved_nodes = []
    saved_currents = []
    first_output = True

    def __init__(self, sram, spfile, corner, initialize=False):
        if OPTS.baseline:
            self.words_per_row = sram.words_per_row
        elif OPTS.serial:
            self.words_per_row = sram.num_cols
        else:
            self.words_per_row = sram.alu_num_words
        super().__init__(sram, spfile, corner, initialize=initialize)

    def create_dut(self):
        dut = SpiceDut(self.sf, self.corner)
        dut.words_per_row = self.words_per_row
        return dut

    def create_probe(self):
        self.probe = BlProbe(self.sram, OPTS.pex_spice)

    def define_signals(self):
        super().define_signals()
        if OPTS.baseline:
            return

        for i in range(self.addr_size):
            self.bus_sigs.append("A_1[{}]".format(i))

        self.bus_selects = ["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor", "s_sum", "s_data"]

        self.inverted_sels = ["s_sr"]
        if OPTS.serial:
            self.inverted_sels.append("sr_en")
            self.bus_selects = ["s_and", "s_nand", "s_or", "s_nor", "s_xor", "s_xnor",
                                "s_sum", "s_data", "s_cout"]
            self.sr_in_selects = ["s_bus", "s_mask_in"]
            self.sr_out_selects = ["s_sr", "s_lsb", "s_msb"]
            self.select_sigs = self.bus_selects + self.sr_in_selects
            bitline_signals = ["en_1", "sr_en", "mask_en", "diff", "diffb"]
        else:
            self.sr_in_selects = ["s_bus", "s_mask_in", "s_shift"]
            self.sr_out_selects = ["s_sr", "s_lsb", "s_msb"]
            self.bus_selects = ["s_and", "s_nand", "s_or", "s_nor", "s_xor",
                                "s_xnor", "s_sum", "s_data"]
            self.select_sigs = self.bus_selects + self.sr_in_selects + self.sr_out_selects
            bitline_signals = ["en_1", "sr_en", "diff", "diffb"]

        self.control_sigs.extend(self.select_sigs + bitline_signals)
        debug.info(1, "Delay control_sigs %s", self.control_sigs)

        if OPTS.serial:
            for i in range(self.num_cols):
                self.bus_sigs.append("c_val[{}]".format(i))
            self.c_val = self.prev_c_val = [0] * self.num_cols
        else:
            for i in range(self.words_per_row):
                self.bus_sigs.append("cin[{}]".format(i))
            self.cin = self.prev_cin = [0] * self.words_per_row

        for sig in self.select_sigs + bitline_signals:
            setattr(self, sig, 0)
            setattr(self, "prev_" + sig, 0)

        self.diff = self.prev_diff = 1
        self.diffb = self.prev_diffb = 0
        mid_address = int(0.5 * self.sram.num_words)
        self.address_1 = self.prev_address_1 = self.convert_address(mid_address)

    def update_address(self):
        super().update_address()
        if OPTS.baseline:
            return
            # write address
        for i in range(self.addr_size):
            key = "A_1[{}]".format(i)
            self.write_pwl(key, self.prev_address_1[i], self.address_1[i])
        self.prev_address_1 = self.address_1

    def get_setup_time(self, key, prev_val, curr_val):
        if key == "sense_trig":
            if self.diff:
                trigger_delay = OPTS.sense_trigger_delay_differential
            else:
                trigger_delay = OPTS.sense_trigger_delay

            if prev_val == 0:
                setup_time = -(self.duty_cycle * self.period + trigger_delay)
            else:
                # This adds some delay to enable tri-state driver
                # For differential sense amp, give some window so data can be read
                if self.diff:
                    setup_time = -(self.period + self.slew + OPTS.sense_trigger_setup)
                else:
                    # no tri-state for bitline computes
                    slack = 0.1
                    # only fall slack after sense_trig_rise or clock rise
                    slack += max(trigger_delay - (1 - self.duty_cycle) * self.period, 0)
                    setup_time = -(self.period + self.duty_cycle * self.period)
            return setup_time
        elif key.startswith("mask["):
            return getattr(OPTS, "mask_setup_time", self.setup_time)

        elif key in ["diff", "diffb"]:
            if self.diffb:
                return - OPTS.diff_setup_time

        return super().get_setup_time(key, prev_val, curr_val)

    def write_pwl(self, key, prev_val, curr_val):
        if key in self.inverted_sels:
            prev_val, curr_val = int(not prev_val), int(not curr_val)
        super().write_pwl(key, prev_val, curr_val)

    def update_cin(self):
        if OPTS.baseline:
            return
        if OPTS.serial:
            for i in range(self.num_cols):
                key = "c_val[{}]".format(i)
                self.write_pwl(key, self.prev_c_val[i], self.c_val[i])
            self.prev_c_val = self.c_val
        else:
            for i in range(self.words_per_row):
                key = "cin[{}]".format(i)
                self.write_pwl(key, self.prev_cin[i], self.cin[i])
            self.prev_cin = self.cin

    def is_signal_updated(self, key):
        if key in ["diff", "diffb"] and not self.read:
            return False
        return super().is_signal_updated(key)

    def update_output(self, increment_time=True):
        self.diffb = int(not self.diff)
        super().update_output(increment_time)
        self.update_cin()

    def probe_delay_addresses(self):
        # TODO addresses to use?
        a_address = self.sram.num_words - 1  # measure using topmost row
        b_address = 0
        c_address = int(self.sram.num_words / 2)
        self.all_addresses = [a_address, b_address, c_address]
        self.probe_all_addresses(self.all_addresses, self.get_delay_probe_cols())

    def generate_delay_steps(self):
        a_address, b_address, c_address = self.all_addresses
        num_cols = self.num_cols

        def select_cols(x):
            if len(x) >= num_cols:
                return x[:num_cols]
            else:
                repeats = ceil(num_cols / len(x))
                return (x * repeats)[:num_cols]

        if OPTS.baseline or getattr(OPTS, "sim_rw_only", False):

            data_one = [1, 0] * int(num_cols / 2)
            data_two = [0, 1] * int(num_cols / 2)
            data_three = [1] * num_cols
            mask_one = [1] * num_cols
            mask_two = [1, 0] * int(num_cols / 2)

            existing_data = {
                a_address: self.invert_vec(data_one),
                b_address: self.invert_vec(data_two),
                c_address: self.invert_vec(data_three),
            }
            self.existing_data = existing_data

            self.setup_write_measurements(a_address)
            self.wr(a_address, data_two, mask_two)

            self.setup_read_measurements(a_address)
            self.rd(a_address)

            self.setup_write_measurements(c_address)
            self.wr(c_address, data_three, mask_one)

            self.setup_read_measurements(b_address)
            self.rd(b_address)

            self.setup_write_measurements(a_address)
            self.wr(a_address, data_two, mask_two)

            self.setup_read_measurements(c_address)
            self.rd(c_address)

            self.setup_write_measurements(b_address)
            self.wr(b_address, data_one, mask_one)

            self.setup_read_measurements(c_address)
            self.rd(c_address)

        else:
            existing_data = {
                a_address: [0, 0, 1, 1] * int(num_cols / 4),
                b_address: [0, 1, 0, 1] * int(num_cols / 4)
            }
            self.existing_data = existing_data
            quick_read = False
            if quick_read:
                self.bank_sel = 1
                self.acc_en = self.read = 1
                self.acc_en_inv = 0
                self.blc(a_address, b_address, b_address)
                self.setup_write_measurements(c_address)
                self.wb(c_address, src="add", cond="mask_in")
                return

            alu_word_size = int(self.num_cols / self.words_per_row)
            mask_one = select_cols([1] * alu_word_size)
            mask_two = select_cols([1] * alu_word_size)
            mask_three = select_cols([1] * alu_word_size + [1, 0] * int(alu_word_size / 2))

            data_one = select_cols([0] * alu_word_size + [1, 1] * int(alu_word_size / 2))
            data_two = select_cols([0] * (alu_word_size - 1) + [1] + [1, 0] * int(alu_word_size / 2))
            data_three = select_cols([1] * alu_word_size + [0, 0] * int(alu_word_size / 2))

            a_data = [data_three[i] if mask_three[i] else data_one[i] for i in range(num_cols)]

            self.wr(a_address, data_one, mask_one)

            self.setup_write_measurements(b_address)
            self.wr(b_address, data_two, mask_two)

            self.setup_write_measurements(a_address)
            self.wr(a_address, data_three, mask_three)

            self.setup_read_measurements(b_address)
            self.rd(b_address)

            # Read A effectively sum =  A + 0
            self.cin = [0] * self.words_per_row
            self.setup_read_measurements(a_address)
            self.rd(a_address)

            # BL compute C = A + B
            self.cin = [1, 0] * max(1, int(self.words_per_row / 2))
            if OPTS.serial:
                c_val = [1, 0] * max(1, int(self.num_cols / 2))
                self.set_c_val(c_val)
            self.blc(a_address, b_address, a_address)

            self.setup_write_measurements(c_address)
            self.wb(c_address, src="add", cond="mask")

            self.sr_en = 1

            # ---- Multiplication -----
            # Read A
            self.setup_read_measurements(a_address)
            # Read A bar into SR to ensure there will be transition when A is later read into it
            mask_in = [int(not x) for x in a_data]
            self.mask = list(reversed(mask_in))
            self.set_selects(sr_in="s_mask_in")
            self.rd(a_address)

            # SR = A ( from previous read )
            self.wb_mask_and()

            # Write back B + C if MSB
            self.blc(b_address, c_address, b_address)
            self.sr_en = 0
            self.setup_write_measurements(c_address)
            self.wb(c_address, src="add", cond="msb")
            # Write back B + C if LSB
            self.blc(b_address, c_address, b_address)
            if not OPTS.serial:
                self.srl()

            self.setup_write_measurements(c_address)

            self.wb(c_address, src="add", cond="lsb")

    def setup_mask_measurements(self):
        clk_buf_probe = self.probe.clk_probes[0]
        for col, col_label in self.mask_probes.items():
            time_suffix = "{:.2g}".format(self.current_time).replace('.', '_')
            meas_name = "mask_col{}_t{}".format(col, time_suffix)
            self.stim.gen_meas_delay(meas_name=meas_name,
                                     trig_name=clk_buf_probe,
                                     trig_val=0.5 * self.vdd_voltage, trig_dir="RISE",
                                     trig_td=self.current_time,
                                     targ_name=col_label,
                                     targ_val=0.5 * self.vdd_voltage, targ_dir="CROSS",
                                     targ_td=self.current_time)

    def set_selects(self, bus_sel=None, sr_in=None, sr_out=None):
        if OPTS.baseline:
            return

        def one_hot_mux(selected, all_sels):
            if selected is None:  # to enable selective sets
                return
            assert selected in all_sels, "Selected {} must be in {}".format(selected, " ".join(all_sels))
            for sig in all_sels:
                if selected == sig:
                    value = 1
                else:
                    value = 0
                setattr(self, sig, value)

        if OPTS.serial:
            one_hot_mux(bus_sel, self.bus_selects)
            one_hot_mux(sr_in, self.sr_in_selects)
            # TODO mask_en set reminder
        else:
            selects = [self.bus_selects, self.sr_in_selects, self.sr_out_selects]
            selected = [bus_sel, sr_in, sr_out]
            for i in range(3):
                one_hot_mux(selected[i], selects[i])

    # uOPS
    def rd(self, addr):
        """Read an address. Address is binary vector"""
        addr_v = self.convert_address(addr)

        self.command_comments.append("* [{: >20}] rd {}\n".format(self.current_time, addr_v))

        self.address = list(reversed(addr_v))

        # Needed signals
        self.bank_sel = 1
        self.read = 1

        self.en_0 = 1
        self.en_1 = 0

        self.diff = 1
        self.diffb = 0

        if OPTS.serial:
            self.mask_en = 0
            self.sr_en = 0
            self.s_cout = 1
        else:
            self.sr_en = 0

        self.set_selects(bus_sel="s_and")

        self.acc_en = 1
        self.acc_en_inv = 0

        self.duty_cycle = self.read_duty_cycle
        self.period = self.read_period

        self.update_output()

        # Reset important signals
        self.bank_sel = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    def wr(self, addr, data_v, mask_v):
        """Write data to an address. Data can be integer or binary vector. Address is binary vector"""
        if not OPTS.energy:
            self.setup_mask_measurements()

        addr_v = self.convert_address(addr)
        # data_v = self.convert_address(data)
        # mask_v = self.convert_address(mask)

        self.command_comments.append("* [{: >20}] wr {}, {}\n".format(self.current_time, addr_v, data_v))

        self.mask = list(reversed(mask_v))
        self.address = list(reversed(addr_v))
        self.data = list(reversed(data_v))

        self.set_selects(bus_sel="s_data", sr_in="s_mask_in", sr_out="s_sr")

        # Needed signals
        self.bank_sel = 1
        self.read = 0

        if OPTS.serial:
            self.mask_en = 1
            self.sr_en = 0
            self.s_cout = 1
        else:
            self.sr_en = 1

        self.en_0 = 1
        self.en_1 = 0

        self.acc_en = 0
        self.acc_en_inv = 1

        self.update_output()

        # Reset important signals
        self.bank_sel = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    def set_mask(self, mask_v):
        self.command_comments.append("* [{: >20}] set_mask {}\n".format(self.current_time, mask_v))

        self.mask = list(reversed(mask_v))

        self.set_selects(sr_in="s_mask_in")

        self.read = 0

        if OPTS.serial:
            self.mask_en = 1
            self.sr_en = 0
            self.s_cout = 1
        else:
            self.sr_en = 1

        self.en_0 = 0
        self.en_1 = 0

        self.acc_en = 0
        self.acc_en_inv = 1

        self.update_output()

        # Reset important signals
        self.bank_sel = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    def blc(self, addr0, addr1, setup_read=None):
        if setup_read:
            if type(setup_read) == bool:
                setup_read = addr0
            self.setup_read_measurements(setup_read)

        self.duty_cycle = OPTS.duty_diffb

        addr0_v = self.convert_address(addr0)
        addr1_v = self.convert_address(addr1)

        self.command_comments.append("* [{: >20}] blc {}, {}\n".format(self.current_time, addr0_v, addr1_v))
        self.log_event("BLC")

        self.address = list(reversed(self.convert_address(addr0_v)))
        self.address_1 = list(reversed(self.convert_address(addr1_v)))

        # Needed signals
        self.bank_sel = 1
        self.read = 1

        self.diff = 0
        self.diffb = 1

        self.en_0 = 1
        self.en_1 = 1

        if OPTS.serial:
            self.mask_en = 0
            self.sr_en = 0
            self.s_cout = 1
        else:
            self.sr_en = 0

        # self.set_selects(bus_sel, sr_in, sr_out)

        self.acc_en = 0
        self.acc_en_inv = 1

        self.update_output()

        # Reset important signals
        self.bank_sel = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0
        self.duty_cycle = OPTS.duty_diff

    def wb(self, addr, src, cond):
        if not OPTS.energy:
            self.setup_mask_measurements()

        addr_v = self.convert_address(addr)

        # Conditional Execution Selection
        if cond == 'msb':
            cond_str = 'if_msb.'
        elif cond == 'lsb':
            cond_str = 'if_lsb.'
        else:
            cond_str = ''

        # Source Selection
        if src == 'and':
            src_str = '.and'
        elif src == 'nand':
            src_str = '.nand'
        elif src == 'nor':
            src_str = '.nor'
        elif src == 'or':
            src_str = '.or'

        elif src == 'xor':
            src_str = '.xor'
        elif src == 'xnor':
            src_str = '.xnor'

        elif src == 'add':
            src_str = '.add'

        elif src == 'data_in':
            src_str = '.data_in'

        else:
            src_str = '.and'

        self.command_comments.append("* [{: >20}] {}wb{} {}\n".format(self.current_time, cond_str, src_str, addr_v))

        self.address = list(reversed(addr_v))
        self.mask = [1] * self.num_cols

        # Generate Signals
        if src == 'and':
            bus_sel = 's_and'
        elif src == 'nand':
            bus_sel = 's_nand'
        elif src == 'nor':
            bus_sel = 's_nor'
        elif src == 'or':
            bus_sel = 's_or'

        elif src == 'xor':
            bus_sel = 's_xor'
        elif src == 'xnor':
            bus_sel = 's_xnor'

        elif src == 'add':
            bus_sel = 's_sum'

        elif src == 'data_in':
            bus_sel = 's_data'

        else:
            bus_sel = 's_and'

        # Conditionals/Masking Signals
        sr_en = 0

        sr_in = 's_mask_in'  # set to mask in, will be disregarded if sr_en=0 anyway

        if cond == 'msb':
            pass
        elif cond == 'lsb':
            pass
        else:
            sr_en = 1

        if cond == 'msb':
            sr_out = 's_msb'
        elif cond == 'lsb':
            sr_out = 's_lsb'
        else:
            sr_out = 's_sr'

        self.set_selects(bus_sel, sr_in, sr_out)

        # Needed signals
        self.bank_sel = 1
        self.read = 0

        self.en_0 = 1
        self.en_1 = 0

        self.acc_en = 0
        self.acc_en_inv = 1

        if OPTS.serial:
            self.mask_en = sr_en
            self.sr_en = 1 if src == 'add' else 0
            self.s_cout = 1
        else:
            self.sr_en = sr_en

        self.update_output()

        # Reset important signals
        self.bank_sel = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    # All possible variants
    def wb_and(self, addr):
        self.wb(addr, 'and', '')

    def if_msb_wb_and(self, addr):
        self.wb(addr, 'and', 'msb')

    def if_lsb_wb_and(self, addr):
        self.wb(addr, 'and', 'lsb')

    def wb_nand(self, addr):
        self.wb(addr, 'nand', '')

    def if_msb_wb_nand(self, addr):
        self.wb(addr, 'nand', 'msb')

    def if_lsb_wb_nand(self, addr):
        self.wb(addr, 'nand', 'lsb')

    def wb_or(self, addr):
        self.wb(addr, 'or', '')

    def if_msb_wb_or(self, addr):
        self.wb(addr, 'or', 'msb')

    def if_lsb_wb_or(self, addr):
        self.wb(addr, 'or', 'lsb')

    def wb_nor(self, addr):
        self.wb(addr, 'nor', '')

    def if_msb_wb_nor(self, addr):
        self.wb(addr, 'nor', 'msb')

    def if_lsb_wb_nor(self, addr):
        self.wb(addr, 'nor', 'lsb')

    def wb_xor(self, addr):
        self.wb(addr, 'xor', '')

    def if_msb_wb_xor(self, addr):
        self.wb(addr, 'xor', 'msb')

    def if_lsb_wb_xor(self, addr):
        self.wb(addr, 'xor', 'lsb')

    def wb_xnor(self, addr):
        self.wb(addr, 'xnor', '')

    def if_msb_wb_xnor(self, addr):
        self.wb(addr, 'xnor', 'msb')

    def if_lsb_wb_xnor(self, addr):
        self.wb(addr, 'xnor', 'lsb')

    def wb_add(self, addr):
        self.wb(addr, 'add', '')

    def if_msb_wb_add(self, addr):
        self.wb(addr, 'add', 'msb')

    def if_lsb_wb_add(self, addr):
        self.wb(addr, 'add', 'lsb')

    def wb_data_in(self, addr):
        self.wb(addr, 'data_in', '')

    def if_msb_wb_data_in(self, addr):
        self.wb(addr, 'data_in', 'msb')

    def if_lsb_wb_data_in(self, addr):
        self.wb(addr, 'data_in', 'lsb')

    # Shift-Register
    def srl(self):
        self.command_comments.append("* [{: >20}] srl\n".format(self.current_time))
        self.log_event("Shift-Register")

        self.set_selects(sr_in='s_shift')

        self.sr_in = 1

        self.read = 0
        self.en_0 = 0
        self.en_1 = 0

        self.acc_en = 0
        self.acc_en_inv = 1

        self.update_output()

        # Reset important signals
        self.bank_sel = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    # CIN
    def set_c_val(self, val):
        if type(val) == int:
            val = [val] * len(self.c_val)

        self.c_val = val

        self.sr_en = 1

        self.read = 0
        self.en_0 = 0
        self.en_1 = 0

        self.acc_en = 0
        self.acc_en_inv = 1

        self.bank_sel = 0

        self.command_comments.append("* [{: >20}] c_val {}\n".format(self.current_time, val))
        self.log_event("c_val")

        self.update_output()

        # Reset important signals
        self.bank_sel = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    def wb_mask(self, src):
        if not OPTS.energy:
            self.setup_mask_measurements()

        # Source Selection
        if src == 'and':
            src_str = '.and'
        elif src == 'nand':
            src_str = '.nand'
        elif src == 'nor':
            src_str = '.nor'
        elif src == 'or':
            src_str = '.or'

        elif src == 'xor':
            src_str = '.xor'
        elif src == 'xnor':
            src_str = '.xnor'

        elif src == 'add':
            src_str = '.add'

        elif src == 'data_in':
            src_str = '.data_in'

        else:
            src_str = '.and'

        self.command_comments.append("* [{: >20}] wb_mask{}\n".format(self.current_time, src_str))

        # Generate Signals
        sr_in = 's_bus'

        if src == 'and':
            bus_sel = 's_and'
        elif src == 'nand':
            bus_sel = 's_nand'
        elif src == 'nor':
            bus_sel = 's_nor'
        elif src == 'or':
            bus_sel = 's_or'

        elif src == 'xor':
            bus_sel = 's_xor'
        elif src == 'xnor':
            bus_sel = 's_xnor'

        elif src == 'add':
            bus_sel = 's_sum'

        elif src == 'data_in':
            bus_sel = 's_data'

        else:
            bus_sel = 's_and'

        self.set_selects(bus_sel=bus_sel, sr_in=sr_in)

        if OPTS.serial:
            self.mask_en = 1
            self.sr_en = 0
            self.s_cout = 1
        else:
            self.sr_en = 1

        self.read = 0
        self.en_0 = 0
        self.en_1 = 0
        self.bank_sel = 0

        self.acc_en = 0
        self.acc_en_inv = 1

        self.update_output()

        # Reset important signals
        self.bank_sel = 0
        self.read = 0
        self.en_0 = self.en_1 = 0
        self.sr_en = 0
        if OPTS.serial:
            self.mask_en = 0

    # All possible variants
    def wb_mask_and(self):
        self.wb_mask('and')

    def wb_mask_nand(self):
        self.wb_mask('nand')

    def wb_mask_or(self):
        self.wb_mask('or')

    def wb_mask_nor(self):
        self.wb_mask('nor')

    def wb_mask_xor(self):
        self.wb_mask('xor')

    def wb_mask_xnor(self):
        self.wb_mask('xnor')

    def wb_mask_add(self):
        self.wb_mask('add')

    def wb_mask_data_in(self):
        self.wb_mask('data_in')

    # Helpers
    def get_random_bin_vector(self, bit_sz):
        MAX_INT = 1 << bit_sz

        _val = random.randint(0, MAX_INT - 1)

        val = []
        for i in range(bit_sz):
            mask = 1 << i
            digit = 0 if (_val & mask) == 0 else 1
            val += [digit]

        return val

    # Macro-Operations
    def add(self):
        num_cols = self.num_cols
        word_size = self.word_size

        def select_cols(x):
            if len(x) >= num_cols:
                return x[:num_cols]
            else:
                repeats = ceil(num_cols / len(x))
                return (x * repeats)[:num_cols]

        data_one = select_cols([0] * word_size + [1, 0, 0, 1] * int(word_size / 4))
        data_two = select_cols([0] * (word_size - 1) + [1] + [1, 0, 1, 0] * int(word_size / 4))
        data_three = select_cols([1] * word_size + [1, 1, 0, 0] * int(word_size / 4))

        mask_all = select_cols([1] * (2 * word_size))

        bit_sz = int(32 / 8)
        MAX_INT = 1 << bit_sz

        A = [random.randint(0, MAX_INT - 1) for i in range(32)]
        B = [random.randint(0, MAX_INT - 1) for i in range(32)]

        C = []
        for a, b in zip(A, B):
            C += [a + b]

        verify_C = [0 for i in range(32)]

        # Load Data
        addr_A = 0 * bit_sz
        addr_B = 1 * bit_sz
        addr_C = 2 * bit_sz

        self.set_c_val(0)

        for bit in range(0, bit_sz):
            mask = 1 << bit
            # A
            data_A = []
            for i in range(32):
                val = 1 if (A[i] & mask) != 0 else 0
                data_A += [val]

            # B
            data_B = []
            for i in range(32):
                val = 1 if (B[i] & mask) != 0 else 0
                data_B += [val]

            # Write data
            self.wr(bit + addr_A, data_A, mask_all)
            self.wr(bit + addr_B, data_B, mask_all)

        # Add two numbers
        for i in range(bit_sz):
            self.blc(addr_A + i, addr_B + i)
            self.wb_add(addr_C + i)

        verify_file = open("verify.data", "w")
        # Verify
        for bit in range(0, bit_sz):
            mask = 1 << bit

            # Read
            self.rd(addr_C + bit)

            # Parse
            # mask   = 1 << bit

            # A
            data_C = []
            for i in range(32):
                val = 1 if (C[i] & mask) != 0 else 0
                data_C += [val]

            self.command_comments.append("* expected = {}\n".format(data_C))
            verify_file.write("[{}, {}],\n".format(self.current_time, data_C))

        verify_file.close()

    def test_wr_rd(self):
        num_cols = self.num_cols
        word_size = self.word_size

        def select_cols(x):
            if len(x) >= num_cols:
                return x[:num_cols]
            else:
                repeats = ceil(num_cols / len(x))
                return (x * repeats)[:num_cols]

        data_one = select_cols([0] * word_size + [1, 0, 0, 1] * int(word_size / 4))
        data_two = select_cols([0] * (word_size - 1) + [1] + [1, 0, 1, 0] * int(word_size / 4))
        data_three = select_cols([1] * word_size + [1, 1, 0, 0] * int(word_size / 4))

        mask_all = select_cols([1] * (2 * word_size))

        bit_sz = int(32 / 8)
        MAX_INT = 1 << bit_sz

        # Load Data
        verify_file = open("verify.data", "w")
        verify_data = []
        for addr in range(0, 8):
            data = self.get_random_bin_vector(32)

            # Write data
            self.wr(addr, data, mask_all)

            # Remember
            verify_data += data

        for data in verify_data:
            # Read the data
            verify_file.write("[{}, {}],\n".format(self.current_time + 1.9, data))
            self.rd(addr)

        verify_file.close()

    def test_blc(self):
        num_cols = self.num_cols
        word_size = self.word_size

        def select_cols(x):
            if len(x) >= num_cols:
                return x[:num_cols]
            else:
                repeats = ceil(num_cols / len(x))
                return (x * repeats)[:num_cols]

        data_one = select_cols([0] * word_size + [1, 0, 0, 1] * int(word_size / 4))
        data_two = select_cols([0] * (word_size - 1) + [1] + [1, 0, 1, 0] * int(word_size / 4))
        data_three = select_cols([1] * word_size + [1, 1, 0, 0] * int(word_size / 4))

        mask_all = select_cols([1] * (2 * word_size))

        bit_sz = int(32 / 8)
        MAX_INT = 1 << bit_sz

        # Load Data
        verify_file = open("verify.data", "w")
        verify_data = []
        for addr in range(0, 2):
            data = self.get_random_bin_vector(32)

            # Write data
            self.wr(addr, data, mask_all)

            # Remember
            verify_data.append([addr, data])

        for entry in verify_data:
            addr = entry[0]
            data = entry[1]

            # Read the data
            self.blc(addr, addr)

            verify_file.write("[{}, {}],\n".format(self.current_time + 1.9, data))
            self.wb_and(addr)

        verify_file.close()
