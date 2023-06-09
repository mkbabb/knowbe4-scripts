#!/bin/zsh

source $HOME/.zshrc

project_dir="$PROGRAMMING_DIR/knowbe4-scripts"

cd $project_dir

poetry run python -m src.report
