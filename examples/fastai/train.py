import sys
sys.path.insert(0, '../..')
from reloading import reloading

from fastai.basic_train import LearnerCallback
from fastai.vision import (URLs, untar_data, ImageDataBunch, 
                           cnn_learner, models, accuracy)


@reloading
def set_learning_rate(learner):
    # Change the learning rate below during the training
    learner.opt.opt.lr = 1e-3
    print('Set LR to', learner.opt.opt.lr)

class LearningRateSetter(LearnerCallback):
    def on_epoch_begin(self, **kwargs):
        set_learning_rate(self.learn)


@reloading
def print_model_statistics(model):
    # Uncomment the following lines after during the training 
    # to start printing statistics
    #
    # print('{: <28}  {: <7}  {: <7}'.format('NAME', ' MEAN', ' STDDEV'))
    # for name, param in model.named_parameters():
    #     mean = param.mean().item()
    #     std = param.std().item()
    #     print('{: <28}  {: 6.4f}  {: 6.4f}'.format(name, mean, std))
    pass

class ModelStatsPrinter(LearnerCallback):
    def on_epoch_begin(self, **kwargs):
        print_model_statistics(self.learn.model)


path = untar_data(URLs.MNIST_SAMPLE)
data = ImageDataBunch.from_folder(path)
learn = cnn_learner(data, models.resnet18, metrics=accuracy, 
                    callback_fns=[ModelStatsPrinter, LearningRateSetter])
learn.fit(10)
