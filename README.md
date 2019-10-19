# reloading
A Python utility to reload a loop body from source on each iteration without
losing state

Useful for editing PyTorch code during training. This lets
you e.g. add logging, print statistics or save the model without restarting the
training and, therefore, without losing the training progress.

![Demo](https://github.com/julvo/reloading/blob/master/example/demo.gif)

## Install
Please make sure you're using Python 3, then install via pip:

```
pip install reloading
```

## Usage

Simply wrap the iterator in a `for` loop with `reloading`, e.g.
```python
from reloading import reloading

for i in reloading(range(10)):
    # here could be your training loop
    print(i)

```
This will reload the loop body from the source file before each iteration.

