#!/bin/sh
./contrib/scripts/build.sh
export SKPY_DEBUG_HTTP=1
#G_DEBUG=fatal_warnings gdb python3.8 -m pumaduct.main -c pumaduct.yaml
#gdb --args ./python3.8m -m pumaduct.main -c pumaduct.yaml
python3.8 -m pumaduct.main -c pumaduct.yaml
./contrib/scripts/clean.sh
