# -*- coding: utf-8 -*-
"""
@author: LONG QIAN
"""


import os 
import numpy as np
import tensorflow as tf

from keras.models import load_model, Model
from keras.optimizers import Adam
from keras.preprocessing.image import ImageDataGenerator, array_to_img, img_to_array, load_img
from keras.callbacks import ModelCheckpoint
from model.params import Params
from model.tec_pre_net import tec_pre_net

def parse_data(serialized_example):
    #return input_img_sequences and output_img_sequences
    features = tf.parse_single_example(
        serialized_example,
        features={
            'input_img_sequences'        : tf.FixedLenFeature([], tf.string),
            'output_img_sequences'       : tf.FixedLenFeature([], tf.string),
            'input_img_sequences_shape'  : tf.FixedLenFeature([4], tf.int64),
            'output_img_sequences_shape' : tf.FixedLenFeature([4], tf.int64)
        }
    )

    input_img_sequences = tf.decode_raw(features['input_img_sequences'], tf.uint8)
    output_img_sequences = tf.decode_raw(features['output_img_sequences'], tf.uint8)

    input_img_sequences_shape  = tf.cast(features['input_img_sequences_shape'], tf.int32)
    output_img_sequences_shape = tf.cast(features['output_img_sequences_shape'], tf.int32)

    input_img_sequences = tf.reshape(input_img_sequences, input_img_sequences_shape)
    output_img_sequences = tf.reshape(output_img_sequences, output_img_sequences_shape)
    #throw input_img_sequences tensor
    # input_img_sequences = tf.cast(input_img_sequences, tf.int32)
    #throw output_img_sequences tensor
    # output_img_sequences = tf.cast(output_img_sequences, tf.int32)

    return input_img_sequences, output_img_sequences


def load_data(filename):
    # create a queue
    # filename_queue = tf.train.string_input_producer([filename])

    # reader = tf.TFRecordReader()
    # return file_name and file
    # _, serialized_example = reader.read(filename_queue)
    dataset = tf.data.TFRecordDataset(filename)
    return dataset.map(parse_data)

    
if __name__ == '__main__':
    cwd = os.getcwd()
    img_rows              = Params.map_rows
    img_cols              = Params.map_cols
    input_time_steps      = Params.input_time_steps
    output_time_steps     = Params.output_length
    nb_train_samples      = 13978
    nb_validation_samples = 1747
    nb_test_samples       = 1748
    nb_epoch              = 10
    batch_size            = Params.batch_size


    training_dataset          = load_data(os.path.join(cwd, 'dataset','ion_training.tfrecords'))
    # training_dataset          = training_dataset.batch(batch_size)
    training_dataset_iterator = training_dataset.make_initializable_iterator()
    training_dataset_iterator_next_element = training_dataset_iterator.get_next()

    validation_dataset          = load_data(os.path.join(cwd, 'dataset','ion_validation.tfrecords'))
    # validation_dataset          = validation_dataset.batch(batch_size)   
    validation_dataset_iterator = validation_dataset.make_initializable_iterator()
    validation_dataset_iterator_next_element = validation_dataset_iterator.get_next()

    model = tec_pre_net((img_rows, img_cols))

    opt = Adam(lr=Params.lr, beta_1=0.9, beta_2=0.999, decay=0.01)
    model.compile(optimizer=opt, loss='mse', metrics=['accuracy'])

    init_op = tf.global_variables_initializer()
    #开始一个会话
    with tf.Session() as sess:         
        sess.run(init_op)
        sess.run(training_dataset_iterator.initializer)
        sess.run(validation_dataset_iterator.initializer)

        input_img_sequences_training = []
        output_img_sequences_training = []
        input_img_sequences_validation = []
        output_img_sequences_validation = []

        try:
            while True:
                input_img_sequences, output_img_sequences = sess.run(training_dataset_iterator_next_element)
                input_img_sequences_training.append(input_img_sequences)
                output_img_sequences_training.append(output_img_sequences)
        except tf.errors.OutOfRangeError:
            print("Training dataset constructed ...")

        try:
            while True:
                input_img_sequences, output_img_sequences = sess.run(validation_dataset_iterator_next_element)
                input_img_sequences_validation.append(input_img_sequences)
                output_img_sequences_validation.append(output_img_sequences)
        except tf.errors.OutOfRangeError:
            print("Validation dataset constructed ...")                 
            
        input_img_sequences_training_fit_x = np.array(input_img_sequences_training)
        output_img_sequences_training_fit_y = np.array(output_img_sequences_training)
        input_img_sequences_validation_fit_x = np.array(input_img_sequences_validation)
        output_img_sequences_validation_fit_y = np.array(output_img_sequences_validation)
        
        # Callback
        checkpointer = ModelCheckpoint(
            filepath=os.path.join(cwd, 'checkpoint', 'TEC_PRE_NET_MODEL_WEIGHTS.{epoch:02d}-{val_acc:.5f}.hdf5'),
            monitor='val_acc',
            verbose=1,
            save_weights_only= True,
            save_best_only=False
        )
        
        model.fit(
            x=input_img_sequences_training_fit_x,
            y=output_img_sequences_training_fit_y,
            epochs=2,
            verbose=1,
            callbacks=[checkpointer],
            validation_data=(input_img_sequences_validation_fit_x, output_img_sequences_validation_fit_y),
            steps_per_epoch=nb_train_samples//batch_size,
            validation_steps=nb_validation_samples//batch_size
        )


# Debug generate_arrays_from_dataset generateor
# for epoch in range(nb_epoch):
#     example_counter = 0
#     print("Epoch " + str(epoch) + '/' + str(nb_epoch))
#     for x, y in (generate_arrays_from_dataset(training_dataset_iterator_next_element)):
#         example_counter = example_counter + 1
#         if (example_counter == 6926):
#             print(example_counter)
#     print("Last Epoch example numble: " + str(example_counter))


# while True:
#     stop = start + batch_size
#     diff = stop - model_input_1.shape[0]
#     if diff <= 0:
#         tec_input  = model_input_1[start:stop]
#         ext_input  = model_input_2[start:stop]
#         tec_output = model_output_1[start:stop]
#         start += batch_size
#     else:
#         tec_input  = np.concatenate((model_input_1[start:], model_input_1[:diff]))
#         ext_input  = np.concatenate((model_input_2[start:], model_input_2[:diff]))
#         tec_output = np.concatenate((model_output_1[start:], model_output_1[:diff]))
#         start = diff
#     yield [tec_input, ext_input], tec_output