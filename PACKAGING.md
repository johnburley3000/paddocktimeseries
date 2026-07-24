# Packaging & release (conda)

All seven packages are `noarch: python` conda packages built from the
`conda/meta.yaml` recipe in each repository. Recipe run-requirements
declare the real conda-forge scientific stack (the slim `pyproject.toml`
deps exist only to keep `pip install -e` fast; conda owns the stack).

## Build (already automated locally)

Build order is core → stores → PaddockTS, against a local output
channel so inter-package deps resolve:

```bash
CH=~/conda-channel
conda build borevitz_lab/conda --output-folder $CH -c conda-forge
for p in pysentinel2 pysilo pyozwald pycopdem pyslga; do
  conda build $p/conda --output-folder $CH -c file://$CH -c conda-forge
done
conda build paddocktimeseries/conda --output-folder $CH \
  -c file://$CH -c conda-forge -c pytorch
```

Each build's `test.imports` runs in a fresh solved env, so a green
build already proves the package installs and imports.

## Publish to anaconda.org

Requires a free [anaconda.org](https://anaconda.org) account. The
channel name is your anaconda.org **username** (assumed
`thestochasticman` below — change if yours differs):

```bash
conda install -n base -c conda-forge anaconda-client
anaconda login                                    # interactive
anaconda upload ~/conda-channel/noarch/*.conda    # all 7 at once
```

After upload the packages are live at
`https://anaconda.org/thestochasticman` and installable by anyone:

```bash
conda create -n paddockts -c conda-forge -c pytorch \
  -c thestochasticman paddocktimeseries
```

## Cutting a new version

1. Bump `version` in the package's `pyproject.toml` **and** its
   `conda/meta.yaml`.
2. Rebuild that package (and any that depend on it) as above.
3. `anaconda upload` the new `.conda` file(s).

## Notes

- **Hardened kernels:** conda-forge's TensorFlow ships shared objects
  that request an executable stack; recent Fedora/glibc refuse to load
  them. See the README's *Hardened-kernel note* for the one-time
  `execstack -c` / `patchelf` fix. This is a conda-forge TF trait, not
  a PaddockTS one.
- **conda-forge (future):** for the widest reach, each package can be
  submitted to conda-forge via `staged-recipes` (needs a PyPI sdist or
  GitHub release per package). The recipes here are a straightforward
  starting point for those feedstocks.
