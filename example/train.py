import time
import sys
sys.path.append('..')
from reloading import reloading

epochs = 10000
loss = 100
model = { 'weights': [0.2, 0.1, 0.4, 0.8, 0.1] }

for i in reloading(range(epochs)):
    time.sleep(2)
    loss /= 2

    print('Epoch:', i, 'Loss:', loss)

