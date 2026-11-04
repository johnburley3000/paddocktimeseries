"""Fractional cover unmixing.

The bundled model weights in `_models/` and the unmixing logic are adapted
from the fractionalcover3 package by Robert Denham, distributed under the
MIT License. See PaddockTS/LICENSES/fractionalcover3.LICENSE.

Each model is a four-layer multilayer perceptron (5 inputs, three ReLU
hidden layers, a linear 3-output layer). The weights were extracted from
the original TensorFlow Lite files and are stored as ``.npz`` archives,
so inference needs only NumPy.
"""
from importlib import resources

import numpy as np


_MODELS = (
    "fcModel_32x32x32.npz",
    "fcModel_64x64x64.npz",
    "fcModel_256x64x256.npz",
    "fcModel_256x128x256.npz",
)


class FractionalCoverModel:
    """A fractional cover MLP: ``layers`` is a list of ``(W, b)`` pairs with
    ``W`` of shape ``(out, in)``. ReLU follows every layer but the last."""

    def __init__(self, layers):
        self.layers = [(np.asarray(W, dtype=np.float32), np.asarray(b, dtype=np.float32))
                       for W, b in layers]

    @property
    def n_inputs(self) -> int:
        return self.layers[0][0].shape[1]

    def __call__(self, x):
        """Apply the network to ``x`` of shape ``(n_pixels, n_inputs)``."""
        h = np.asarray(x, dtype=np.float32)
        last = len(self.layers) - 1
        for i, (W, b) in enumerate(self.layers):
            h = h @ W.T
            h += b
            if i < last:
                np.maximum(h, 0, out=h)
        return h


def get_model(n: int = 2) -> FractionalCoverModel:
    """Load the n-th bundled fractional cover model (1-indexed, 1-4)."""
    path = resources.files(__package__) / "_models" / _MODELS[n - 1]
    with resources.as_file(path) as p, np.load(p) as z:
        n_layers = sum(1 for k in z.files if k.startswith("W"))
        layers = [(z[f"W{i}"], z[f"b{i}"]) for i in range(n_layers)]
    return FractionalCoverModel(layers)


def unmix_fractional_cover(surface_reflectance, fc_model, in_null=0, out_null=0):
    """Unmix a 6-band surface reflectance array into bare/green/non-green fractions.

    The blue band is dropped before inference (the model was trained on the
    remaining 5 bands). Returns a (3, nrows, ncols) float32 array.
    """
    inshape = surface_reflectance[1:].shape
    ref_data = np.reshape(surface_reflectance[1:], (inshape[0], -1)).T
    fc_layers = fc_model(ref_data).T
    output_fc = np.reshape(fc_layers, (3, inshape[1], inshape[2]))
    output_fc[output_fc == in_null] = out_null
    return output_fc
