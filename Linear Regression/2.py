
# 线性回归

import tensorflow as tf
import numpy as np
import random
import matplotlib.pyplot as plt

# 获得数据 / 10 只是让数据好看一点
def getBatch(batchSize,start=None):
    if start==None:    
        start = random.randint(1, 10000)
    n = np.linspace(start, start+batchSize, batchSize, endpoint=True).reshape((batchSize,1)) / 10
    x = np.sin(n)
    y = np.cos(n)
    return x,y,n

# 增加层 w1 * x * x + w2 * x + b
def add_layer(inputs, in_size, out_size, activation_function=None):
    Weights1 = tf.Variable(tf.random_normal([in_size, out_size]))
    Weights2 = tf.Variable(tf.random_normal([in_size, out_size]))
    biases = tf.Variable(tf.zeros([out_size]) + 0.1)
    Wx_plus_b = tf.matmul(inputs * inputs, Weights1) + \
                tf.matmul(inputs, Weights2) + \
                biases
    if activation_function is None:
        outputs = Wx_plus_b
    else:
        outputs = activation_function(Wx_plus_b)
    return outputs

# 神经网络定义
def neural_networks():
    x = tf.placeholder(tf.float32, [None, 1], name='x')
    y = tf.placeholder(tf.float32, [None, 1], name='y')   
    layer = add_layer(x, 1, 200, tf.nn.relu)
    prediction = add_layer(layer, 200, 1)
    cost = tf.reduce_sum(tf.square(y - prediction))
    optimizer = tf.train.AdamOptimizer(0.001).minimize(cost)
    return x, y, prediction, optimizer, cost

if __name__ == '__main__':
    x, y, prediction, optimizer, cost = neural_networks()
    sess = tf.Session()
    init = tf.global_variables_initializer()
    sess.run(init)
    plt.ion()
    plt.show()
    for i in range(100000):
        batch_x, batch_y, batch_n= getBatch(200,0)
        _, loss, pred = sess.run([optimizer, cost, prediction], feed_dict={x: batch_x, y: batch_y})
        if i % 50 == 0 :
            print(i, loss)
            plt.clf()
            plt.plot(batch_n, batch_y, 'r', batch_n, pred, 'b')
            plt.ylim((-1.2, 1.2))        
            plt.draw()
            plt.pause(0.1)
