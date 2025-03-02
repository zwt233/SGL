from sgl.models.base_model import BaseSGAPModel
from sgl.models.simple_models import LogisticRegression
from sgl.operators.graph_op import LaplacianGraphOp
from sgl.operators.message_op import MeanMessageOp


class SSGC(BaseSGAPModel):
    def __init__(self, prop_steps, feat_dim, num_classes):
        super(SSGC, self).__init__(prop_steps, feat_dim, num_classes)

        self._pre_graph_op = LaplacianGraphOp(prop_steps, r=0.5)
        self._pre_msg_op = MeanMessageOp(start=0, end=prop_steps + 1)
        self._base_model = LogisticRegression(feat_dim, num_classes)
