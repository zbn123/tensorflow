# coding=utf-8
# 中文OCR学习

import tensorflow as tf
import numpy as np
import os
from utils import readImgFile, img2vec, show
import time
import random

curr_dir = os.path.dirname(__file__)

# 图片的高度为12X256，宽度为不定长
image_size = (12,256)

#LSTM
num_hidden = 64
num_layers = 1

# 所有 unicode CJK统一汉字（4E00-9FBB） + CJK统一汉字扩充A（3400-4DB5） + ascii的字符加 + blank + ctc blank
# https://zh.wikipedia.org/wiki/Unicode
# https://zh.wikipedia.org/wiki/ASCII
# num_classes = 20924 + 6582 + (126 - 32) + 1 + 1
# unicode 5.0 99089 个字符
num_classes = 99089 + 1 + 1

#初始化学习速率
LEARNING_RATE = 1e-4
DECAY_STEPS = 5000
REPORT_STEPS = 500
MOMENTUM = 0.9

BATCHES = 100
BATCH_SIZE = 64
TRAIN_SIZE = BATCHES * BATCH_SIZE
TEST_BATCH_SIZE = 10

print("Loading data ...")
train_files = open(os.path.join(curr_dir, "data", "index.txt")).readlines()

def neural_networks():
    # 输入：训练的数量，一张图片的宽度，一张图片的高度 [-1,-1,12]
    inputs = tf.placeholder(tf.float32, [None, None, image_size[0]])
    # 定义 ctc_loss 是稀疏矩阵
    labels = tf.sparse_placeholder(tf.int32)
    # 1维向量 序列长度 [batch_size,]
    seq_len = tf.placeholder(tf.int32, [None])
    # 定义 LSTM 网络
    # 可以为:
    #   tf.nn.rnn_cell.RNNCell
    #   tf.nn.rnn_cell.GRUCell
    cell = tf.contrib.rnn.LSTMCell(num_hidden, state_is_tuple=True)
    stack = tf.contrib.rnn.MultiRNNCell([cell] * num_layers, state_is_tuple=True)
    
    # 第二个输出状态，不会用到
    outputs, _ = tf.nn.dynamic_rnn(stack, inputs, seq_len, dtype=tf.float32)

    shape = tf.shape(inputs)

    batch_s, max_timesteps = shape[0], shape[1]
    # Reshaping to apply the same weights over the timesteps
    outputs = tf.reshape(outputs, [-1, num_hidden])

    W = tf.Variable(tf.truncated_normal([num_hidden, num_classes], stddev=0.1), name="W")
    b = tf.Variable(tf.constant(0., shape=[num_classes]), name="b")

    logits = tf.matmul(outputs, W) + b
    logits = tf.reshape(logits, [batch_s, -1, num_classes])

    logits = tf.transpose(logits, (1, 0, 2))
    return logits, inputs, labels, seq_len, W, b


# 生成一个训练batch
def get_next_batch(batch_size=128):
    inputs = np.zeros([batch_size, image_size[1], image_size[0]])
    codes = []

    batch = random.sample(train_files, batch_size)

    for i, line in enumerate(batch):
        lines = line.split(" ")
        imageFileName = lines[0]+".png"
        text = lines[1].strip()
        image = readImgFile(os.path.join(curr_dir,"data",imageFileName))
        image_vec = img2vec(image,image_size[0],image_size[1])
        #np.transpose 矩阵转置 (12*256,) => (12,256) => (256,12)
        inputs[i,:] = np.transpose(image_vec.reshape((image_size[0],image_size[1])))
        #标签转成列表保存在codes
        text_list = [ord(char) for char in text]
        codes.append(text_list)
    #比如batch_size=2，两条数据分别是"12"和"1"，则labels [['1','2'],['1']]

    labels = [np.asarray(i) for i in codes]
    #labels转成稀疏矩阵
    sparse_labels = sparse_tuple_from(labels)
    #(batch_size,) sequence_length值都是256，最大划分列数
    seq_len = np.ones(inputs.shape[0]) * image_size[1]
    return inputs, sparse_labels, seq_len

# 转化一个序列列表为稀疏矩阵    
def sparse_tuple_from(sequences, dtype=np.int32):
    indices = []
    values = []
    
    for n, seq in enumerate(sequences):
        indices.extend(zip([n] * len(seq), range(len(seq))))
        values.extend(seq)
 
    indices = np.asarray(indices, dtype=np.int64)
    values = np.asarray(values, dtype=dtype)
    shape = np.asarray([len(sequences), np.asarray(indices).max(0)[1] + 1], dtype=np.int64)

    return indices, values, shape

def decode_sparse_tensor(sparse_tensor):
    decoded_indexes = list()
    current_i = 0
    current_seq = []
    for offset, i_and_index in enumerate(sparse_tensor[0]):
        i = i_and_index[0]
        if i != current_i:
            decoded_indexes.append(current_seq)
            current_i = i
            current_seq = list()
        current_seq.append(offset)
    decoded_indexes.append(current_seq)
    result = []
    for index in decoded_indexes:
        result.append(decode_a_seq(index, sparse_tensor))
    return result
    
def decode_a_seq(indexes, spars_tensor):
    decoded = []
    for m in indexes:
        str = spars_tensor[1][m]
        decoded.append(str)
    return decoded

def list_to_chars(list):
    return "".join([chr(v) for v in list])

def train():
    global_step = tf.Variable(0, trainable=False)
    logits, inputs, labels, seq_len, W, b = neural_networks()

    loss = tf.nn.ctc_loss(labels=labels,inputs=logits, sequence_length=seq_len)
    cost = tf.reduce_mean(loss)

    # optimizer = tf.train.MomentumOptimizer(learning_rate=LEARNING_RATE, momentum=MOMENTUM).minimize(cost, global_step=global_step)
    optimizer = tf.train.AdamOptimizer(learning_rate=LEARNING_RATE).minimize(cost,global_step=global_step)
    decoded, log_prob = tf.nn.ctc_beam_search_decoder(logits, seq_len, merge_repeated=False)
    acc = tf.reduce_mean(tf.edit_distance(tf.cast(decoded[0], tf.int32), labels))

    init = tf.global_variables_initializer()

    def report_accuracy(decoded_list, test_labels):
        original_list = decode_sparse_tensor(test_labels)
        detected_list = decode_sparse_tensor(decoded_list)
        true_numer = 0
        
        if len(original_list) != len(detected_list):
            print("len(original_list)", len(original_list), "len(detected_list)", len(detected_list),
                  " test and detect length desn't match")
            return
        print("T/F: original(length) <-------> detectcted(length)")
        for idx, number in enumerate(original_list):
            detect_number = detected_list[idx]
            hit = (number == detect_number)
            print(hit, list_to_chars(number), "(", len(number), ") <-------> ", list_to_chars(detect_number), "(", len(detect_number), ")")
            if hit:
                true_numer = true_numer + 1
        print("Test Accuracy:", true_numer * 1.0 / len(original_list))

    def do_report():
        test_inputs,test_labels,test_seq_len = get_next_batch(TEST_BATCH_SIZE)
        test_feed = {inputs: test_inputs,
                     labels: test_labels,
                     seq_len: test_seq_len}
        dd, log_probs, accuracy = session.run([decoded[0], log_prob, acc], test_feed)
        report_accuracy(dd, test_labels)
 
    def do_batch():
        train_inputs, train_labels, train_seq_len = get_next_batch(BATCH_SIZE)
        
        feed = {inputs: train_inputs, labels: train_labels, seq_len: train_seq_len}
        
        b_loss,b_labels, b_logits, b_seq_len,b_cost, steps, _ = session.run([loss, labels, logits, seq_len, cost, global_step, optimizer], feed)

        if steps > 0 and steps % REPORT_STEPS == 0:
            do_report()
        return b_cost, steps

    def restore(sess):
        curr_dir = os.path.dirname(__file__)
        model_dir = os.path.join(curr_dir, "model")
        if not os.path.exists(model_dir): os.mkdir(model_dir)
        saver_prefix = os.path.join(model_dir, "model.ckpt")        
        ckpt = tf.train.get_checkpoint_state(model_dir)
        saver = tf.train.Saver(max_to_keep=5)
        if ckpt and ckpt.model_checkpoint_path:
            print("Restore Model ...")
            saver.restore(sess, ckpt.model_checkpoint_path)
        return saver, model_dir, saver_prefix

    with tf.Session() as session:
        session.run(init)
        saver, model_dir, checkpoint_path = restore(session) # tf.train.Saver(tf.global_variables(), max_to_keep=100)
        while True:            
            train_cost = train_ler = 0
            for batch in range(BATCHES):
                start = time.time()
                c, steps = do_batch()
                train_cost += c * BATCH_SIZE
                seconds = time.time() - start
                print("Step:", steps, ", Cost:", c, ", batch seconds:", seconds)
            
            # train_cost /= TRAIN_SIZE
            
            # train_inputs, train_labels, train_seq_len = get_next_batch(BATCH_SIZE)
            # val_feed = {inputs: train_inputs,
            #             labels: train_labels,
            #             seq_len: train_seq_len}

            # val_cost, val_ler, lr, steps = session.run([cost, acc, learning_rate, global_step], feed_dict=val_feed)

            # log = "Epoch {}/{}, steps = {}, train_cost = {:.3f}, train_ler = {:.3f}, val_cost = {:.3f}, val_ler = {:.3f}, time = {:.3f}s, learning_rate = {}"
            # print(log.format(curr_epoch + 1, num_epochs, steps, train_cost, train_ler, val_cost, val_ler, time.time() - start, lr))
            saver.save(session, checkpoint_path, global_step=steps)

if __name__ == '__main__':
    os.environ["CUDA_VISIBLE_DEVICES"] = "1"
    train()