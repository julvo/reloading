import time
import sys
sys.path.append('..')

from reloading import reloading


loss = 100
model = {
    'weights': 123
    }

epochs = 10000
for i in reloading(range(epochs)):
    time.sleep(1)

    model['weights'] += 1
    loss /= 2.

    print('Epoch:', i, 'Loss:', loss)

print(model)
