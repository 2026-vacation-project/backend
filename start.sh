#!/usr/bin/env bash

source ./venv/bin/activate
python -m uvicorn main:app --reload
deactivate
