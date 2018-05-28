#!/usr/bin/env python
# coding: utf-8
import time
import sys
import argparse
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.autograd import Variable
import numpy as np
import math
import pickle
import os
import torch
import torch.nn as nn
dtype = torch.cuda.FloatTensor
import time


class softmax(nn.Module):
    def __init__(self, W):
        super(softmax, self).__init__()
        self.W = Variable(torch.from_numpy(W).type(dtype), requires_grad=True)

    def forward(self, x, y):
        # calculate loss for the loss function and L2 regularizer
        D = (torch.matmul(x,self.W))
        D_max,_ = torch.max(D,dim = 1, keepdim = True)
        D = D-D_max
        A = torch.log(torch.sum(torch.exp(D),dim = 1))
        B = torch.sum(D*y,dim=1)
        Phi = torch.sum(A-B)
        W1 = torch.squeeze(self.W)
        L2 = torch.sum(torch.mul(W1, W1))
        return (Phi,L2)

def softmax_np(x):
    e_x = np.exp(x - np.max(x,axis = 1,keepdims = True))
    return e_x / e_x.sum(axis = 1,keepdims = True)

def load_data(dataset):
    if dataset == "Cifar":
        with open("data/weight_323436.pkl", "rb") as input_file:
            [W_32,W_34,W_36,intermediate_output_32,intermediate_output_34,intermediate_output_36] = pickle.load(input_file, encoding = 'latin1')
        print('done loading')
        model = softmax(W_36)
        model.cuda()
        start = time.time()
        return (np.concatenate([intermediate_output_34,np.ones((intermediate_output_34.shape[0],1))],axis = 1), intermediate_output_36, model)
    elif dataset == "AwA":
        with open("data/weight_bias.pickle", "rb") as input_file:
            [weight,bias] = pickle.load(input_file,encoding = 'latin1')
        train_feature = np.squeeze(np.load('data/train_feature.npy'))
        train_output = np.squeeze(np.load('data/train_output.npy'))
        weight = np.transpose(np.concatenate([weight,np.expand_dims(bias,1)],axis = 1))
        train_feature = np.concatenate([train_feature,np.ones((train_feature.shape[0],1))],axis = 1)
        train_output = softmax_np(train_output)
        model = softmax(weight)
        model.cuda()
        return (train_feature,train_output,model)

def to_np(x):
    return x.data.cpu().numpy()

def backtracking_line_search(optimizer,model,grad,x,y,val,beta,N,args):
    t = 1.0
    W_O = to_np(model.W)
    grad_np = to_np(grad)
    while(True):
        model.W = Variable(torch.from_numpy(W_O-t*grad_np).type(dtype), requires_grad=True)
        val_n = 0.0
        (Phi,L2) = model(x,y)
        val_n = Phi/N + L2*args.lmbd
        if t < 0.000001 :
            break
        if to_np(val_n - val + t*torch.norm(grad)**2/2)>=0:
            t = beta *t
        else:
            break

def train(X, Y, model, args):
    x = Variable(torch.FloatTensor(X).cuda())
    y = Variable(torch.FloatTensor(Y).cuda())
    N = len(Y)
    min_loss = 10000.0
    optimizer = optim.SGD([model.W],lr = 1.0)
    for epoch in range(args.epoch):
        sum_loss = 0
        phi_loss = 0
        optimizer.zero_grad()
        (Phi,L2) = model(x,y)
        loss = L2*args.lmbd + Phi/N
        phi_loss += to_np(Phi/N)
        loss.backward()
        z = model.W.grad
        temp_W = model.W.data
        backtracking_line_search(optimizer,model,model.W.grad,x,y,loss,0.5,N,args)
        grad_loss = to_np(torch.mean(torch.abs(z)))
        if grad_loss < min_loss:
            if epoch ==0:
                init_grad = grad_loss
            min_loss = grad_loss
            best_W = temp_W
            if min_loss < init_grad/200:
                print('stopping criteria reached')
                print(epoch)
                sys.stdout.flush()
                break
        if epoch % 100 == 0:
            print('Epoch:{:4d}\tloss:{}\tphi_loss:{}\tgrad:{}'.format(epoch, to_np(loss), phi_loss, grad_loss))
            #sys.stdout.flush()
    temp = torch.matmul(x,Variable(best_W))
    max_value,_ = torch.max(temp,1,keepdim = True)
    temp = temp-max_value
    D_exp = torch.exp(temp)
    D_exp_sum = torch.sum(D_exp, dim=1).view(N,1)
    weight_matrix = D_exp.div(D_exp_sum.expand_as(D_exp))-y
    weight_matrix = torch.div(weight_matrix,(-2.0*args.lmbd*N))
    w = torch.matmul(torch.t(x),weight_matrix)

    temp = torch.matmul(x,w.cuda())
    max_value,_ = torch.max(temp,1,keepdim = True)
    temp = temp-max_value
    D_exp = torch.exp(temp)
    D_exp_sum = torch.sum(D_exp, dim=1).view(N,1)
    y_p = to_np(D_exp.div(D_exp_sum.expand_as(D_exp)))

    temp = torch.matmul(x,Variable(best_W))
    max_value,_ = torch.max(temp,1,keepdim = True)
    temp = temp-max_value
    D_exp = torch.exp(temp)
    D_exp_sum = torch.sum(D_exp, dim=1).view(N,1)
    y_pp = to_np(D_exp.div(D_exp_sum.expand_as(D_exp)))

    #print('diff')
    #print(np.mean(np.abs(to_np(y)-y_p)))
    #print(np.mean(np.abs(to_np(y)-y_pp)))
    from scipy.stats.stats import pearsonr
    print('pearson correlation between ground truth and prediction')
    y = to_np(y)
    corr,_ = (pearsonr(y.flatten(),(y_p).flatten()))
    print(corr)
    sys.stdout.flush()
    return to_np(weight_matrix)

def main(args):
    x,y,model = load_data(args.dataset)
    start = time.time()
    weight_matrix = train(x,y,model,args)
    end = time.time()
    print('computational time')
    print(end-start)
    np.savez("weight_matrix_{}".format(args.dataset),weight_matrix = weight_matrix)
    with open("weight_matrix_{}.pkl".format(args.dataset), "wb") as output_file:
        pickle.dump([weight_matrix], output_file, protocol=pickle.HIGHEST_PROTOCOL)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lmbd', type=float, default=0.003)
    parser.add_argument('--epoch', type=int, default=2000)
    parser.add_argument('--dataset', type=str, default="Cifar")
    args = parser.parse_args()
    print(args)
    main(args)
