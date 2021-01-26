from globals import OPTS
from modules.baseline_latched_control_buffers import LatchedControlBuffers as BaseLatchedControlBuffers
from modules.logic_buffer import LogicBuffer


class LatchedControlBuffers(BaseLatchedControlBuffers):
    """
    Difference with baseline is that this only enables precharge during reads.
    Since all columns will be written for writes when there is no column mux,
        only enable precharge during reads
        (add additional read input to make it nand3 instead of nand3)
    """

    def create_schematic_connections(self):
        connections = super().create_schematic_connections()
        precharge_conn = ["read", "bank_sel", "clk", "precharge_en", "precharge_en_bar"]
        self.replace_connection("precharge_buf", precharge_conn, connections)
        return connections

    def create_precharge_buffers(self):
        assert len(OPTS.precharge_buffers) % 2 == 0, "Number of precharge buffers should be even"
        self.precharge_buf = self.create_mod(LogicBuffer, buffer_stages=OPTS.precharge_buffers,
                                             logic="pnand3")
