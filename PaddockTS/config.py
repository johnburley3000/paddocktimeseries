"""Compatibility shim: Config moved to the shared borevitz_lab package."""
from borevitz_lab.config import Config, config  # noqa: F401

if __name__ == '__main__':
    print(config)
