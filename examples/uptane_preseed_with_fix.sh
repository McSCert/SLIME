#!/usr/bin/env bash

# learn the system under test
config=uptane_preseed_with_fix/config.json
slime $config --setup
slime $config --pre-startup
gnome-terminal --tab -e "bash -c \"slime $config -m 0; exec bash\""
echo 'Press any key to continue...'; read -n1;
gnome-terminal --tab -e "bash -c \"slime $config -m 1; exec bash\""
echo 'Press any key to continue...'; read -n1;
gnome-terminal --tab -e "bash -c \"slime $config -m 2; exec bash\""
echo 'Press any key to continue...'; read -n1;
gnome-terminal --tab -e "bash -c \"slime $config -m 3; exec bash\""
echo 'Press any key to continue...'; read -n1;
gnome-terminal --tab -e "bash -c \"slime $config -m 4; exec bash\""
echo 'Press any key to continue...'; read -n1;
gnome-terminal --tab -e "bash -c \"slime $config -s 0; exec bash\""
echo 'Press any key to continue...'; read -n1;
gnome-terminal --tab -e "bash -c \"slime $config -s 1; exec bash\""
echo 'Press any key to continue...'; read -n1;
gnome-terminal --tab -e "bash -c \"slime $config -l; slime $config -f; exec bash\""
echo 'Press any key to continue...'; read -n1;
gnome-terminal --tab -e "bash -c \"slime $config --statelearner; exec bash\""
echo 'System learning has started.'
