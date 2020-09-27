#/bin/bash
./contrib/scripts/build.sh
find pumaduct -name "*.py" | xargs pylint
./contrib/scripts/clean.sh
