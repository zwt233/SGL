import numpy as np
import random
import torch
from sklearn.cluster import KMeans

from sgl.tasks.clustering_metrics import clustering_metrics


def accuracy(output, labels):
    pred = output.max(1)[1].type_as(labels)
    correct = pred.eq(labels).double()
    correct = correct.sum()
    return (correct / len(labels)).item()


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def evaluate(model, val_idx, test_idx, labels, device):
    model.eval()
    val_output = model.model_forward(val_idx, device)
    test_output = model.model_forward(test_idx, device)

    acc_val = accuracy(val_output, labels[val_idx])
    acc_test = accuracy(test_output, labels[test_idx])
    return acc_val, acc_test


def mini_batch_evaluate(model, val_idx, val_loader, test_idx, test_loader, labels, device):
    model.eval()
    correct_num_val, correct_num_test = 0, 0
    for batch in val_loader:
        val_output = model.model_forward(batch, device)
        pred = val_output.max(1)[1].type_as(labels)
        correct_num_val += pred.eq(labels[batch]).double().sum()
    acc_val = correct_num_val / len(val_idx)

    for batch in test_loader:
        test_output = model.model_forward(batch, device)
        pred = test_output.max(1)[1].type_as(labels)
        correct_num_test += pred.eq(labels[batch]).double().sum()
    acc_test = correct_num_test / len(test_idx)

    return acc_val.item(), acc_test.item()


def train(model, train_idx, labels, device, optimizer, loss_fn):
    model.train()
    optimizer.zero_grad()

    train_output = model.model_forward(train_idx, device)
    loss_train = loss_fn(train_output, labels[train_idx])
    acc_train = accuracy(train_output, labels[train_idx])
    loss_train.backward()
    optimizer.step()

    return loss_train.item(), acc_train


def mini_batch_train(model, train_idx, train_loader, labels, device, optimizer, loss_fn):
    model.train()
    correct_num = 0
    loss_train_sum = 0.
    for batch in train_loader:
        train_output = model.model_forward(batch, device)
        loss_train = loss_fn(train_output, labels[batch])

        pred = train_output.max(1)[1].type_as(labels)
        correct_num += pred.eq(labels[batch]).double().sum()
        loss_train_sum += loss_train.item()

        optimizer.zero_grad()
        loss_train.backward()
        optimizer.step()

    loss_train = loss_train_sum / len(train_loader)
    acc_train = correct_num / len(train_idx)

    return loss_train, acc_train.item()


def cluster_loss(train_output, y_pred, cluster_centers):
    for i in range(len(cluster_centers)):
        if i == 0:
            dist = torch.norm(train_output - cluster_centers[i], p=2, dim=1, keepdim=True)
        else:
            dist = torch.cat((dist, torch.norm(train_output - cluster_centers[i], p=2, dim=1, keepdim=True)), 1)

    loss = 0.
    loss_tmp = -dist.mean(1).sum()
    loss_tmp += 2 * np.sum(dist[j, x] for j, x in zip(range(dist.shape[0]), y_pred))
    loss = loss_tmp / dist.shape[0]
    return loss


def clustering_train(model, train_idx, labels, device, optimizer, loss_fn, n_clusters, n_init):
    model.train()
    optimizer.zero_grad()

    train_output = model.model_forward(train_idx, device)

    # calc loss
    kmeans = KMeans(n_clusters=n_clusters, n_init=n_init)
    y_pred = kmeans.fit_predict(train_output.data.cpu().numpy())  # cluster_label
    cluster_centers = torch.FloatTensor(kmeans.cluster_centers_).to(device)

    loss_train = loss_fn(train_output, y_pred, cluster_centers)
    loss_train.backward()
    optimizer.step()

    # calc acc, nmi, adj
    labels = labels.cpu().numpy()
    cm = clustering_metrics(labels, y_pred)
    acc, nmi, adjscore = cm.evaluationClusterModelFromLabel()

    return loss_train.item(), acc, nmi, adjscore
