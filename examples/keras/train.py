# Example taken from https://keras.io/getting-started/sequential-model-guide/#examples
import sys
sys.path.insert(0, '../..')
from reloading import reloading

import keras
from keras import backend as K
from keras.models import Sequential
from keras.layers import Dense, Activation
from keras.optimizers import SGD
from keras.callbacks import Callback


@reloading
def set_learning_rate(model):
    # Change the below value during training and see how it updates
    K.set_value(model.optimizer.lr, 1e-3)
    print('Set LR to', K.get_value(model.optimizer.lr))

class LearningRateSetter(Callback):
    def on_epoch_begin(self, epoch, logs=None):
        set_learning_rate(self.model)


# Generate dummy data
import numpy as np
x_train = np.random.random((10000, 20))
y_train = keras.utils.to_categorical(np.random.randint(10, size=(10000, 1)), num_classes=10)
x_test = np.random.random((1000, 20))
y_test = keras.utils.to_categorical(np.random.randint(10, size=(1000, 1)), num_classes=10)

model = Sequential()
model.add(Dense(64, activation='relu', input_dim=20))
model.add(Dense(10, activation='softmax'))

sgd = SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
model.compile(loss='categorical_crossentropy',
              optimizer=sgd,
              metrics=['accuracy'])

model.fit(x_train, y_train,
          epochs=200,
          batch_size=128,
          callbacks=[LearningRateSetter()])
score = model.evaluate(x_test, y_test, batch_size=128)