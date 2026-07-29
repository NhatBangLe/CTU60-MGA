#!/usr/bin/env bash

ENV=${1:-ctu}
COLLECTION=${2:-book}
DATA_DIR=${3:-./data/news}

CONDA_ROOT=$(conda info --base)
source $CONDA_ROOT/etc/profile.d/conda.sh
conda activate $ENV

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(dirname "$SCRIPT_DIR")"

cd "$WORK_DIR"

python -m app.cli add --collection "$COLLECTION" --data-dir "$DATA_DIR"

read -p "Press enter to exit"