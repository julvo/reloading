import sys
sys.path.insert(0, '../..')
from reloading import reloading

from torch import nn
from torch.optim import Adam
import torch.nn.functional as F
from torchvision.models import resnet18
from torchvision.datasets import FashionMNIST
from torchvision.transforms import ToTensor
from torch.utils.data import DataLoader
from tqdm import tqdm


dataset = FashionMNIST('.', download=True, transform=ToTensor())
dataloader = DataLoader(dataset, batch_size=8)

model = resnet18(pretrained=True)
model.fc = nn.Linear(model.fc.in_features, 10)

optimiser = Adam(model.parameters())

for epoch in reloading(range(1000)):
    # Try to change the code inside this loop during the training and see how the
    # changes are applied without restarting the training

    model.train()
    losses = []

    for images, targets in tqdm(dataloader):
        losses.append(1)

        optimiser.zero_grad()
        predictions = model(images.expand(8, 3, 28, 28))
        loss = F.cross_entropy(predictions, targets)
        loss.backward()
        optimiser.step()
        losses.append(loss.item())

    # Here would be your validation code

    print(f'Epoch {epoch} - Loss {sum(losses) / len(losses)}')


