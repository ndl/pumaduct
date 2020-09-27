#!/bin/sh
python setup.py build
cp build/lib.linux-x86_64-3.8/pumaduct/*.so pumaduct
