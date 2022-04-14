#!/bin/bash
set -ex

mypy socketsundso examples
flake8 socketsundso examples
black socketsundso examples --check
isort socketsundso examples scripts --check-only
