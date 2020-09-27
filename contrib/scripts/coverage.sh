#!/bin/sh
./contrib/scripts/build.sh
coverage run -m unittest discover -s pumaduct -p "*_test.py"
coverage report -m
./contrib/scripts/clean.sh
