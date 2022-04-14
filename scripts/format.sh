#!/bin/bash
set -ex

autoflake --remove-all-unused-imports --recursive --remove-unused-variables --in-place socketsundso examples tests --exclude=__init__.py
black socketsundso examples tests
isort socketsundso examples tests
