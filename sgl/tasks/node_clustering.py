import time
import torch
from sklearn.cluster import KMeans
from sqlalchemy import null
from torch.optim import Adam

from sgl.tasks.base_task import BaseTask
from sgl.tasks.clustering_metrics import clustering_metrics
from sgl.tasks.utils import set_seed, clustering_train, cluster_loss


class NodeClustering(BaseTask):
    def __init__(self, dataset, model, lr, weight_decay, epochs, device, loss_fn=cluster_loss, seed=42,
                 train_batch_size=None, eval_batch_size=None, n_init=20):
        super(NodeClustering, self).__init__()

        # clustering task does not support batch training
        if train_batch_size is not None or eval_batch_size is not None:
            raise ValueError("clustering task does not support batch training")

        self.__dataset = dataset
        self.__labels = self.__dataset.y

        self.__model = model
        self.__optimizer = Adam(model.parameters(), lr=lr,
                                weight_decay=weight_decay)
        self.__epochs = epochs
        self.__loss_fn = loss_fn
        self.__device = device
        self.__seed = seed

        # clustering task does not need valid set
        self.__cluster_train_idx = torch.arange(0, self.__dataset.num_node, dtype=torch.long)

        # params for Kmeans
        # note that the n_clusters should be equal to the number of different labels
        self.__n_clusters = self.__dataset.num_classes
        self.__n_init = n_init

        self._acc, self._nmi, self._adjscore = self._execute()

    @property
    def acc(self):
        return self._acc

    @property
    def nmi(self):
        return self._nmi

    @property
    def adjscore(self):
        return self._adjscore

    def _execute(self):
        set_seed(self.__seed)

        pre_time_st = time.time()
        self.__model.preprocess(self.__dataset.adj, self.__dataset.x)
        pre_time_ed = time.time()
        print(f"Preprocessing done in {(pre_time_ed - pre_time_st):.4f}s")

        self.__model = self.__model.to(self.__device)
        self.__labels = self.__labels.to(self.__device)

        t_total = time.time()
        best_acc = 0.
        best_nmi = 0.
        best_adjscore = 0.

        for epoch in range(self.__epochs):
            t = time.time()

            loss_train, acc, nmi, adjscore = clustering_train(self.__model, self.__cluster_train_idx, self.__labels,
                                                              self.__device, self.__optimizer, self.__loss_fn,
                                                              self.__n_clusters, self.__n_init)

            print("Epoch: {:03d}".format(epoch + 1),
                  "loss_train: {:.4f}".format(loss_train),
                  "acc: {:.4f}".format(acc),
                  "nmi: {:.4f}".format(nmi),
                  "adjscore: {:.4f}".format(adjscore),
                  "time: {:.4f}s".format(time.time() - t)
                  )

            if acc > best_acc:
                best_acc = acc
            if nmi > best_nmi:
                best_nmi = nmi
            if adjscore > best_adjscore:
                best_adjscore = adjscore

        # postprocess
        acc, nmi, adjscore = self._postprocess()
        if acc > best_acc:
            best_acc = acc
        if nmi > best_nmi:
            best_nmi = nmi
        if adjscore > best_adjscore:
            best_adjscore = adjscore

        print("Optimization Finished!")
        print("Total time elapsed: {:.4f}s".format(time.time() - t_total))
        print(f"Best acc: {best_acc:.4f}, best_nmi: {best_nmi:.4f}, best_adjscore: {best_adjscore:.4f}")

        return best_acc, best_nmi, best_adjscore

    def _postprocess(self):
        self.__model.eval()
        outputs = self.__model.model_forward(
            range(self.__dataset.num_node), self.__device).to("cpu")

        final_output = self.__model.postprocess(self.__dataset.adj, outputs)
        kmeans = KMeans(n_clusters=self.__n_clusters, n_init=self.__n_init)
        y_pred = kmeans.fit_predict(final_output.data.cpu().numpy())  # cluster_label

        labels = self.__labels.cpu().numpy()
        cm = clustering_metrics(labels, y_pred)
        acc, nmi, adjscore = cm.evaluationClusterModelFromLabel()

        return acc, nmi, adjscore
