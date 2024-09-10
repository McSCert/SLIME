# [SLIME: State Learning in the Middle of Everything](#slime)
- [Installation](#installation)
- [Usage](#usage)

## [Installation](#installation)
- Install SLIME using setup.py with python3
```
python3 setup.py install --user
```
- Guided installation of dependencies (tested on Ubuntu 22.04)
```
slime --install
```

## [Usage](#usage)
0. Help pages and readme (these instructions)
   - `slime -h`
   - `slime.diff -h`
   - `slime.fsmproduct -h`
   - `slime.label -h`
   - `slime.legend -h`
   - `slime.logck -h`
   - `slime.logcleaner -h`
   - `slime.msgexamples -h`
   - `slime.pretty -h`
   - `slime.states -h`
   - `slime.trace -h`
   - `slime.trace_stats -h`
   - `slime --readme`
1. Guided install of slime dependencies
   - `slime --install`
2. Guided setup of system under test and learning environment
   - `slime <config file> --setup`
   - `slime <config file> --learner-setup`
3. Run any pre-startup commands (usually just starts rabbitmq in the background, required after system reboot)
   - `slime <config file> --pre-startup`
4. Startup mitmproxy controller(s), run each in a separate terminal
   - `slime <config file> -m 0`
   - `slime <config file> -m 1`
   - `slime <config file> -m ...`
5. Startup SUT controller(s), run each in a separate terminal
   - `slime <config file> -s 0`
   - `slime <config file> -s 1`
   - `slime <config file> -s ...`
6. Start SLIME in learnlib mode in a separate terminal
   - `slime <config file> -l`
7. Start statelearner in a separate terminal
   - `slime <config file> --statelearner`
8. Cleanup when finished
   - `slime <config file> -f`
   - wait a few seconds for it to clear all queues and kill SUT(s)
   - send SIGINT to all running terminal windows

