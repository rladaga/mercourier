#!/bin/bash

DEPENDENCIES="python python-pip python-virtualenv"

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if command -v apt &> /dev/null; then
        sudo apt install -y $DEPENDENCIES
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y $DEPENDENCIES
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm $DEPENDENCIES
    else
        echo "Unsupported package manager, you can request adding it via pull request"
        exit 1
    fi

elif [[ "$OSTYPE" == "darwin"* ]]; then

    if command -v brew &> /dev/null; then
        brew install $DEPENDENCIES
    else
        echo "brew is required, please install it"
        exit 1
    fi

else
    echo "Unsupported OS: $OSTYPE, install the dependencies manually"
    exit 1
fi
