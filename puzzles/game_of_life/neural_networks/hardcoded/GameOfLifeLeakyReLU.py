import torch
import torch.nn as nn

from neural_networks.hardcoded.GameOfLifeHardcoded import GameOfLifeHardcoded


class GameOfLifeLeakyReLU(GameOfLifeHardcoded):
    """
    LeakyReLU can see in both directions, thus can (sometimes) solve both the logic and output layers
    ReLU1 and tanh has problems with this, however the LeakyReLU solution is less easy for a human to understand
    All activation functions have a hard time solving the counter layer
    LeakyReLU trained solution:
    with sigmoid output:
        logic.weight     [[  -0.002864,   1.094667 ]
                          [ -17.410564, -14.649882 ]]
        logic.bias        [  -3.355898,   9.621474 ]
        output.weight     [  -3.801134,  -6.304538 ]
        output.bias          -2.024391,
    with ReLU1 output (starting with sigmoid weights):
        logics.0.weight  [[   0.029851,   1.03208 ]
                          [ -17.687109, -14.95262 ]]
        logics.0.bias:    [  -3.499570,   9.46179 ]
        output.weight:    [  -3.968801,  -6.47038 ]
        output.bias          -1.865675
    """
    def __init__(self):
        super().__init__()

        self.trainable_layers  = [ 'logics', 'output' ]
        self.input   = nn.Conv2d(in_channels=1, out_channels=1, kernel_size=(1, 1), bias=False)  # no-op trainable layer
        self.counter = nn.Conv2d(in_channels=1, out_channels=2, kernel_size=(3,3),
                                  padding=1, padding_mode='circular', bias=False)
        self.logics  = nn.ModuleList([
            nn.Conv2d(in_channels=2, out_channels=2, kernel_size=(1,1))
        ])
        self.output  = nn.Conv2d(in_channels=2, out_channels=1, kernel_size=(1,1))
        self.activation = nn.LeakyReLU()



    def forward(self, x):
        x = input = self.cast_inputs(x)

        x = self.input(x)     # noop - a single node linear layer - torch needs at least one trainable layer
        x = self.counter(x)   # counter counts above 6, so no ReLU6

        for logic in self.logics:
            x = logic(x)
            x = self.activation(x)

        x = self.output(x)
        x = torch.sigmoid(x) # MAR we want a sigmoid to facilitate gradient
        #x = ReLU1()(x)  # we actually want a ReLU1 activation for binary outputs

        return x

    @property
    def filename(self) -> str:
        if os.environ.get('KAGGLE_KERNEL_RUN_TYPE'):
            return f'./{self.__class__.__name__}.pth'
        else:
            return os.path.join( os.path.dirname(__file__), 'models', f'{self.__class__.__name__}.pth' )


    # DOCS: https://pytorch.org/tutorials/beginner/saving_loading_models.html
    def save(self, verbose=True):
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        torch.save(self.state_dict(), self.filename)
        if verbose: print(f'{self.__class__.__name__}.savefile(): {self.filename} = {humanize.naturalsize(os.path.getsize(self.filename))}')
        return self


    def load(self, load_weights=True, verbose=True):
        if load_weights and os.path.exists(self.filename):
            try:
                self.load_state_dict(torch.load(self.filename))
                if verbose: print(f'{self.__class__.__name__}.load(): {self.filename} = {humanize.naturalsize(os.path.getsize(self.filename))}')
            except Exception as exception:
                # Ignore errors caused by model size mismatch
                if verbose: print(f'{self.__class__.__name__}.load(): model.load throws exception {exception}\n')
                if verbose: print(f'{self.__class__.__name__}.load(): model has changed dimensions, reinitializing weights\n')
                #self.apply(self.weights_init)
                self.hard_code
        else:
            if verbose:
                if load_weights: print(f'{self.__class__.__name__}.load(): model file not found, reinitializing weights\n')
                # else:          print(f'{self.__class__.__name__}.load(): reinitializing weights\n')
            #self.apply(self.weights_init)
            self.hard_code

        self.loaded = True    # prevent any infinite if self.loaded loops
        self.to(self.device)  # ensure all weights, either loaded or untrained are moved to GPU
        self.eval()           # default to production mode - disable dropout
        self.freeze()         # default to production mode - disable training
        return self

    def hard_code(self):
        super().load()

        self.input.weight.data   = torch.tensor([[[[1.0]]]])
        self.counter.weight.data = torch.tensor([
            [[[ 0.0, 0.0, 0.0 ],
              [ 0.0, 1.0, 0.0 ],
              [ 0.0, 0.0, 0.0 ]]],

            [[[ 1.0, 1.0, 1.0 ],
              [ 1.0, 0.0, 1.0 ],
              [ 1.0, 1.0, 1.0 ]]]
        ])

        self.logics[0].weight.data = torch.tensor([
            [ [[   0.2 ]], [[   1.0  ]] ],
            [ [[ -17.9 ]], [[ -15.1  ]] ],
        ])
        self.logics[0].bias.data = torch.tensor([
            -3.6,
             9.1
        ])

        # AND == Both sides need to be positive
        self.output.weight.data = torch.tensor([
            [ [[-4.0 ]], [[-6.5 ]] ],
        ])
        self.output.bias.data = torch.tensor([ -1.8 ])  # Either both Alive or both Dead statements must be true

        self.to(self.device)
        return self


if __name__ == '__main__':
    from neural_networks.train import train
    import numpy as np

    model = GameOfLifeLeakyReLU()

    board = np.array([
        [0,0,0,0,0],
        [0,0,0,0,0],
        [0,1,1,1,0],
        [0,0,0,0,0],
        [0,0,0,0,0],
    ])
    result1 = model.predict(board)
    result2 = model.predict(result1)

    train(model)

    result3 = model.predict(board)
    result4 = model.predict(result1)
    assert np.array_equal(board, result4)

    print('-' * 20)
    print(model.__class__.__name__)
    for name, parameter in sorted(model.named_parameters(), key=lambda pair: pair[0].split('.')[0] ):
        print(name)
        print(parameter.data.squeeze().cpu().numpy())
        print()
