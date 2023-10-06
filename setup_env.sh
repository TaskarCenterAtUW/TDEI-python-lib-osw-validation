#!/bin/bash
env_name="tdei"
# check if conda exists in the system
conda_path=$(command -v conda)
echo $conda_path
echo "Checking if conda is installed on the system ..."
if [ -z "$conda_path" ]; then
    echo " conda not found on the system"
    echo " !!! Please install conda on your system before proceeding ..."
    exit 1
else
    echo " Found conda at $conda_path"
fi

echo "Checking if the environment already exists ..."
if conda env list | grep -q "$env_name"; then
    echo " !!! $env_name already exists in the system. Exiting..."
    exit 1
fi

echo "Creating $env_name environment with conda ..."
yes | conda create -n $env_name python=3.10

echo "Activating $env_name ..."
source ~/anaconda3/etc/profile.d/conda.sh
conda activate $env_name

echo "Installing required packages using pip in $env_name ..."
pip install -r requirements.txt

echo "***********************************************"
echo "TDEI environment setup and activation complete."
echo "***********************************************"
