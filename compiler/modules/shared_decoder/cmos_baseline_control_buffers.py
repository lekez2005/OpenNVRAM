from globals import OPTS
from modules.baseline_latched_control_buffers import LatchedControlBuffers as BaseLatchedControlBuffers
from modules.logic_buffer import LogicBuffer


class LatchedControlBuffers(BaseLatchedControlBuffers):
    """
    Difference with baseline is that baseline only enables precharge during reads.
    To prevent write errors, bitline need to be precharged even for un-selected columns
    So, for words_per_row > 1, precharge when bank is selected and clk is high independent of read or write
    """
    def create_precharge_buffers(self):
        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        logic_args = self.get_logic_args()
        self.precharge_buf = LogicBuffer(buffer_stages=OPTS.precharge_buffers, logic="pnand2", **logic_args)
        self.add_mod(self.precharge_buf)

    def connect_inst(self, args, check=True):
        if "precharge_en_bar" in args:
            args = args[1:]
        super().connect_inst(args, check)

    def route_precharge_buf(self):
        # route precharge_buf_inst
        self.connect_a_pin(self.precharge_buf_inst, self.bank_sel_pin, via_dir="right")
        self.connect_b_pin(self.precharge_buf_inst, self.clk_pin, via_dir="left")
