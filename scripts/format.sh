#!/bin/bash
set -ex

autoflake --remove-all-unused-imports --recursive --remove-unused-variables --in-place socketsundso examples --exclude=__init__.py
black socketsundso examples
isort socketsundso examples
