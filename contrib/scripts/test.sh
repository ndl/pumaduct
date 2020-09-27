#!/bin/sh
./contrib/scripts/build.sh
python -m unittest discover -s pumaduct -p "*_test.py"
./contrib/scripts/clean.sh
