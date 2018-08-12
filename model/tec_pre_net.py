from keras.layers import (
    Input,
    TimeDistributed,
    Lambda
)
from keras.layers.convolutional import Convolution2D
from keras.layers.convolutional_recurrent import ConvLSTM2D
from keras.layers.normalization import BatchNormalization
from keras.models import Model
from keras.layers.merge import Concatenate
from keras.utils import plot_model

from .params import Params




def get_conv_layer(input_time_steps, layer_name, kernel_size=(3, 3), nb_filter=32, channels=32):
    #对每个time_step的tec_map做卷积计算
    conv_layer = Convolution2D(nb_filter, kernel_size, padding="same",name=layer_name, activation="relu")
    time_dis_conv_layer = TimeDistributed(conv_layer, input_shape=(input_time_steps, Params.map_rows, Params.map_cols, channels))

    return conv_layer, time_dis_conv_layer


def get_conv_block(input_time_steps, kernel_size=(3, 3), nb_filter=32, repetations=4):
    layer_list = []
    time_dis_layer_list = []
    size = kernel_size[0]
    for i in range(repetations):
        layer_name = "conv_{0}*{0}_{1}".format(size, i)
        conv_layer, time_dis_conv_layer = get_conv_layer(input_time_steps, layer_name, kernel_size, nb_filter, nb_filter)
        layer_list.append(conv_layer)
        time_dis_layer_list.append(time_dis_conv_layer)

    return layer_list, time_dis_layer_list


def tec_pre_net(tec_map_shape, input_time_steps=36, output_time_steps=24, external_dim=4):
    rows, cols = tec_map_shape
    #对于tensorflow后端，通道数在最后
    input = Input(shape=(input_time_steps, rows, cols, 1), name='data')

    #多尺度编码
    nb_filter = Params.conv_nb_filter

    conv33_layer, time_dis_conv33_layer = get_conv_layer(input_time_steps, layer_name="conv_3*3", kernel_size=(3, 3), nb_filter=nb_filter, channels=1)
    encoder_conv33_layers, encoder_conv33_block = get_conv_block(input_time_steps, kernel_size=(3, 3), nb_filter=nb_filter, repetations=3)
    x_0 = time_dis_conv33_layer(input)
    for layer in encoder_conv33_block:
        x_0 = layer(x_0)

    conv55_layer, time_dis_conv55_layer = get_conv_layer(input_time_steps, layer_name="conv_5*5", kernel_size=(5, 5), nb_filter=nb_filter, channels=1)
    encoder_conv55_layers, encoder_conv55_block = get_conv_block(input_time_steps, kernel_size=(5, 5), nb_filter=nb_filter, repetations=3)
    x_1 = time_dis_conv55_layer(input)
    for layer in encoder_conv55_block:
        x_1 = layer(x_1)

    conv77_layer, time_dis_conv77_layer = get_conv_layer(input_time_steps, layer_name="conv_7*7", kernel_size=(7, 7), nb_filter=nb_filter, channels=1)
    encoder_conv77_layers, encoder_conv77_block = get_conv_block(input_time_steps, kernel_size=(7, 7), nb_filter=nb_filter, repetations=3)
    x_2 = time_dis_conv77_layer(input)
    for layer in encoder_conv77_block:
        x_2 = layer(x_2)

    #TODO: 是否需要对卷积结果做降维？决定之后ConvLSTM2D的input_shape中最后一维
    conv_lstm_33_layer = ConvLSTM2D(filters=nb_filter,
                              kernel_size=(3, 3),
                              padding='same',
                              return_sequences=True,
                              #stateful=True,
                              batch_input_shape=(1, 1, 1),
                              input_shape=(None, rows, cols, nb_filter))
    conv_33 = conv_lstm_33_layer(x_0)

    conv_lstm_55_layer = ConvLSTM2D(filters=nb_filter,
                              kernel_size=(5, 5),
                              padding='same',
                              return_sequences=True,
                              #stateful=True,
                              input_shape=(None, rows, cols, nb_filter))
    conv_55 = conv_lstm_55_layer(x_1)

    conv_lstm_77_layer = ConvLSTM2D(filters=nb_filter,
                              kernel_size=(7, 7),
                              padding='same',
                              return_sequences=True,
                              #stateful=True,
                              input_shape=(None, rows, cols, nb_filter))
    conv_77 = conv_lstm_77_layer(x_2)

    #解码
    decoder_conv33_layers, decoder_conv33_block = get_conv_block(input_time_steps, kernel_size=(3, 3), nb_filter=nb_filter, repetations=4)
    for layer in decoder_conv33_block:
        conv_33 = layer(conv_33)

    decoder_conv55_layers, decoder_conv55_block = get_conv_block(input_time_steps, kernel_size=(5, 5), nb_filter=nb_filter, repetations=4)
    for layer in decoder_conv55_block:
        conv_55 = layer(conv_55)

    decoder_conv77_layers, decoder_conv77_block = get_conv_block(input_time_steps, kernel_size=(7, 7), nb_filter=nb_filter, repetations=4)
    for layer in decoder_conv77_block:
        conv_77 = layer(conv_77)

    stacked = Concatenate(axis=-1)([conv_33, conv_55, conv_77])

    dim_reduce = Convolution2D(1, (3,3), padding="same", name="conv_1*1", activation="relu")
    time_dis_dim_reduce = TimeDistributed(dim_reduce, input_shape=(input_time_steps, rows, cols, 3 * nb_filter))

    sequences = time_dis_dim_reduce(stacked)

    #提取最后一步的预测值
    new_step = Lambda(lambda x: x[:, -1:, :, :, :])(sequences)

    prediction_list = [new_step]

    # 将预测值迭代输入网络
    for i in range(output_time_steps - 1):
        new_x_0 = TimeDistributed(conv33_layer, input_shape=(1, Params.map_rows, Params.map_cols, 1))(new_step)
        for layer in encoder_conv33_layers:
            new_x_0 = TimeDistributed(layer, input_shape=(1, Params.map_rows, Params.map_cols, nb_filter))(new_x_0)

        new_x_1 = TimeDistributed(conv55_layer, input_shape=(1, Params.map_rows, Params.map_cols, 1))(new_step)
        for layer in encoder_conv55_layers:
            new_x_1 = TimeDistributed(layer, input_shape=(1, Params.map_rows, Params.map_cols, nb_filter))(new_x_1)

        new_x_2 = TimeDistributed(conv77_layer, input_shape=(1, Params.map_rows, Params.map_cols, 1))(new_step)
        for layer in encoder_conv77_layers:
            new_x_2 = TimeDistributed(layer, input_shape=(1, Params.map_rows, Params.map_cols, nb_filter))(new_x_2)

        new_conv_33 = conv_lstm_33_layer(new_x_0)
        new_conv_55 = conv_lstm_55_layer(new_x_1)
        new_conv_77 = conv_lstm_77_layer(new_x_2)

        for layer in decoder_conv33_layers:
            new_conv_33 = TimeDistributed(layer, input_shape=(1, Params.map_rows, Params.map_cols, nb_filter))(new_conv_33)

        for layer in decoder_conv55_layers:
            new_conv_55 = TimeDistributed(layer, input_shape=(1, Params.map_rows, Params.map_cols, nb_filter))(new_conv_55)

        for layer in decoder_conv77_layers:
            new_conv_77 = TimeDistributed(layer, input_shape=(1, Params.map_rows, Params.map_cols, nb_filter))(new_conv_77)

        new_stacked = Concatenate(axis=-1)([new_conv_33, new_conv_55, new_conv_77])
        new_time_dis_dim_reduce = TimeDistributed(dim_reduce, input_shape=(1, rows, cols, 3 * nb_filter))
        new_step = new_time_dis_dim_reduce(new_stacked)
        prediction_list.append(new_step)

    predictions = Concatenate(axis=1, name="final_concatenate")(prediction_list)

    model = Model(input, predictions)
    return model




if __name__ == '__main__':
    model = tec_pre_net((Params.map_rows, Params.map_cols))
    plot_model(model, to_file='./TecMapPreNet.svg', show_shapes=True)
    model.summary()
