#!/usr/bin/env bash

# learn the system under test
config=simple_food_order_base/config.json
slime $config --pre-startup
gnome-terminal --tab -e "bash -c \"slime $config -m 0; exec bash\""
echo 'Press any key to continue...'; read -n1;
gnome-terminal --tab -e "bash -c \"slime $config -s 0; exec bash\""
echo 'Press any key to continue...'; read -n1;
gnome-terminal --tab -e "bash -c \"slime $config -s 1; exec bash\""
echo 'Press any key to continue...'; read -n1;
gnome-terminal --tab -e "bash -c \"slime $config -l -a; slime $config -f; exec bash\""
echo 'Press any key to continue...'; read -n1;
gnome-terminal --tab -e "bash -c \"slime $config --statelearner; exec bash\""
echo 'System learning has started.'
