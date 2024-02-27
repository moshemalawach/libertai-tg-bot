#!/bin/bash

# Install virtualenv if not installed
if ! [ -x "$(command -v virtualenv)" ]; then
  echo 'Error: virtualenv is not installed.' >&2
  echo 'Installing virtualenv...'
  pip install virtualenv
fi

virtualenv venv

source venv/bin/activate
pip install -r requirements.txt

deactivate

exit 0