#!/bin/bash
set -ex

mypy socketsundso examples
flake8 socketsundso examples tests
black socketsundso examples tests --check
isort socketsundso examples scripts tests --check-only
