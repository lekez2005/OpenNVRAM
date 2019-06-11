from importlib import reload

from modules.cam.matchline_precharge import matchline_precharge


class sf_matchline_precharge(matchline_precharge):

    def create_layout(self):
        # use bigger bitcell temporarily, layout will be fixed to support shorter bitcells
        class_file = reload(__import__('cam_bitcell_12t'))
        self.bitcell = getattr(class_file, 'cam_bitcell_12t')()
        super().create_layout()
