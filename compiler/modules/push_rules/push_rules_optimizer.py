from characterizer.control_buffers_optimizer import ControlBufferOptimizer
from modules.horizontal.logic_buffer_horizontal import LogicBufferHorizontal


class PushRulesOptimizer(ControlBufferOptimizer):
    def extract_wordline_buffer_load(self, driver_mod, net, buffer_stages_str):
        # create a placeholder driver
        logic_buffer = LogicBufferHorizontal(buffer_stages=driver_mod.buffer_stages, logic="pnand2")
        buffer_index = logic_buffer.insts.index(logic_buffer.buffer_inst)
        logic_buffer.insts[buffer_index].mod = driver_mod.logic_buffer
        driver_mod.logic_buffer = logic_buffer
        return super().extract_wordline_buffer_load(driver_mod, net, buffer_stages_str)
