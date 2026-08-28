"""Konftest: współdzielone fixture scorer."""
import os

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@pytest.fixture(scope="session")
def scorer():
    from scraper.filters import Scorer

    def load(name):
        with open(os.path.join(ROOT, "config", name), encoding="utf-8") as f:
            return yaml.safe_load(f)

    return Scorer(load("keywords.yaml"), load("cpv.yaml"), load("weights.yaml"), load("sources.yaml"))
