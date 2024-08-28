#!/bin/bash

read -p "Enter the netuid argument [18]: " netuid
netuid=${netuid:-18}

read -p "Enter the wallet.name argument [default]: " wallet_name
wallet_name=${wallet_name:-default}

read -p "Enter the wallet.hotkey argument [default]: " wallet_hotkey
wallet_hotkey=${wallet_hotkey:-default}

read -p "Log to wandb? higly recommended [true]: " wandb_on
wandb_on=${wandb_on:-true}

read -p "What logging level? (info/debug/trace) [debug]: " log
log=${log:-debug}

read -p "pm2 name? [validator]: " pm2_name
pm2_name=${pm2_name:-validator}

read -p "Subtensor endpoint? for testing: wss://test.finney.opentensor.ai:443/ [wss://entrypoint-finney.opentensor.ai:443]: " subtensor_address
subtensor_address=${subtensor_address:-wss://entrypoint-finney.opentensor.ai:443}

read -p "Autoupdate? [true]: " autoupdate
autoupdate=${autoupdate:-true}

command_to_run="pm2 start python3 --name $pm2_name -- -m validators.validator --subtensor.chain_endpoint $subtensor_address--netuid $netuid --wallet.name $wallet_name --wallet.hotkey $wallet_hotkey --autoupdate $autoupdate"

command_to_run="$command_to_run --logging.$log"

if [ "$wandb_on" = "false" ]; then
    command_to_run="$command_to_run --wandb_off"
fi

# Run the Python script with the provided arguments
echo $command_to_run
$command_to_run "$@"