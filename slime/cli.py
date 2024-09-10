# Standard library
import textwrap
import socket
import csv
import time
import os
import sys
import subprocess
import shlex
import signal
import code
import pdb
import traceback
import time
import argparse
import json
import typing
import logging
import multiprocessing
import pickle

# Third party
from loguru import logger

# Local
from .utils import readJson, loguru_decorator

def guided_cmds(cmds: list):
    for cmd in cmds:
        print("\033[94m> %s\033[0m" % (cmd))
        response = input("\033[92mRun command (yes/NO)?\033[0m ")
        if response.strip().lower().startswith("y"):
            subprocess.run(shlex.split(cmd))

def guided_install():
    cmds = {
        "manjaro": [
            ["sudo pamac update"],
            ["sudo pamac install graphviz intellij-idea-community-edition mitmproxy docker rabbitmq bcc bcc-tools python-bcc"],
            ["sudo pamac build criu jdk8-adoptopenjdk"], # "systemtap-git"
            ["sudo systemctl start docker"],
            ["sudo rabbitmq-plugins enable rabbitmq_management"],
            ["echo you can login to the rabbitmq dashboard via localhost:15672 guest/guest"]
        ],
        "ubuntu": [
            ["echo The guided installation is for Ubuntu based distros, and was tested on Ubuntu 22.04 LTS, note you may need a PPA with a newer version of python3-bpfcc for tracing to work"],
            ["sudo apt update"],
            ["sudo apt install git openjdk-11-jdk maven graphviz docker.io rabbitmq-server bpfcc-tools python3-bpfcc"],
            ["sudo systemctl start docker"],
            ["sudo rabbitmq-plugins enable rabbitmq_management"]
        ]
    }
    # response = input("\033[92mSelect a distro to be guided through the install commands:\n%s\n>\033[0m " % ("\n".join(cmds.keys())))
    response = "ubuntu"
    guided_cmds(cmds[response.lower()])

def guided_setup(config_file: str):
    config = readJson(config_file)
    response = input("\033[92mGenerate mitmproxy addon(s) (yes/NO)?\033[0m ")
    if response.strip().lower().startswith("y"):
        base_path = os.path.dirname(__file__)
        for mitm in config["mitm_controllers"]:
            if "addon_name" in config["mitm_controllers"][mitm]:
                addon_name = config["mitm_controllers"][mitm]["addon_name"]  # could also extract this from the cmd, but they could change the flag at some point and break this then, could also be a user customized module that shouldn't be touched
                with open(os.path.join(base_path, "mitmproxyaddon.py"), "r") as f:
                    addon = f.read().replace("MITM_NAME", mitm)
                    if "rabbit_credentials" in config["mitm_controllers"][mitm]:
                        addon = addon.replace("RABBIT_CREDENTIALS", config["mitm_controllers"][mitm]["rabbit_credentials"])
                    else:
                        addon = addon.replace(", RABBIT_CREDENTIALS", "")
                    if "addon_protocol" in config["mitm_controllers"][mitm]:
                        if config["mitm_controllers"][mitm]["addon_protocol"].lower() == "http":
                            addon = addon.replace("# choose HttpManager() or TcpManager()", "HttpManager()")
                        elif config["mitm_controllers"][mitm]["addon_protocol"].lower() == "tcp":
                            addon = addon.replace("# choose HttpManager() or TcpManager()", "TcpManager()")
                        elif config["mitm_controllers"][mitm]["addon_protocol"].lower() == "udp":
                            addon = addon.replace("# choose HttpManager() or TcpManager()", "TcpManager()")
                            addon = addon.replace("tcp", "udp").replace("TCP", "UDP").replace("Tcp", "Udp")
                        else:
                            print("Invalid protocol specified for mitmproxy addon, must be http or tcp", file=sys.stderr)
                            sys.exit(1)
                    else:
                        addon = addon.replace("# choose HttpManager() or TcpManager()", "HttpManager()")
                with open(addon_name, "w") as f:
                    f.write(addon)
        print("\033[94mDone!\033[0m")
    response = input("\033[92mSystem under test setup (build) (yes/NO)?\033[0m ")
    if response.strip().lower().startswith("y"):
        guided_cmds(config["environment_setup"]["build_cmds"])

def statelearner_setup(config_file: str):
    config = readJson(config_file)
    response = input("\033[92mStatelearner setup (build) (yes/NO)?\033[0m ")
    if response.strip().lower().startswith("y"):
        guided_cmds(config["environment_setup"]["statelearner_setup"])

def guided_pre_startup(config_file: str):
    config = readJson(config_file)
    response = input("\033[92mEnvironment setup (startup) (yes/NO)?\033[0m ")
    if response.strip().lower().startswith("y"):
        guided_cmds(config["environment_setup"]["startup_cmds"])

def start_statelearner(config):
    config = readJson(config)
    subprocess.run(shlex.split(config["slime_config"]["statelearner_cmd"]))

def config_validator(config):
    # basically just check all required fields exist, maybe type check as well, and for loop to check every sut/mitm
    pass

def instructions():
    print(textwrap.dedent("""
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
       - if any containers are still running, `sudo docker stop <container> && sudo docker container prune`
    """))

def main() -> int:
    # argparse
    readme = ("MITM Learning Server")
    parser = argparse.ArgumentParser(description=readme)
    parser.add_argument("config", action="store", type=str, nargs="?",
                        help="path to config file (json)")
    parser.add_argument("-m", action="store", metavar="mitm_index", type=int, default=None,
                        help="startup mitmproxy by index")
    parser.add_argument("-mm", action="store", metavar="mitm_name", type=str,
                        help="startup mitmproxy by name")
    parser.add_argument("-s", action="store", metavar="sut_index", type=int, default=None,
                        help="startup system under test (SUT) controller by index")
    parser.add_argument("-ss", action="store", metavar="sut_name", type=str,
                        help="startup system under test (SUT) controller by name")
    parser.add_argument("-l", action="store_true",
                        help="run slime in learnlib mode")
    parser.add_argument("-r", action="store_true",
                        help="resume learnlib mode (loads and replays last log)")
    parser.add_argument("-a", action="store_true",
                        help="load alphabet symbols from logs/output_alphabet.json and logs/output_alphabet_examples.json (so the alphabet doesn't change between systems for diffing)")
    parser.add_argument("-c", action="store_true",
                        help="run slime with custom queries from logs/queries.csv")
    parser.add_argument("-i", action="store_true",
                        help="interactive mode: pause before each command to select next action")
    parser.add_argument("-n", action="store_true",
                        help="no run: instantiates variables then enters interactive shell")
    parser.add_argument("-f", action="store_true",
                        help="finished learning, run this after each session to cleanup and kill mitmproxy")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="verbose logging (warning, using with enable_tracing will cause it to hang after a few minutes due to too much output)")
    parser.add_argument("--auto", action="store_true",
                        help="auto start: NOT IMPLEMENTED YET (warning, can't open in separate terminal windows)")
    parser.add_argument("--readme", action="store_true",
                        help="print usage from readme")
    parser.add_argument("--install", action="store_true",
                        help="guided installation of dependencies for slime on manjaro (run 'sudo pamac update' first)")
    parser.add_argument("--setup", action="store_true",
                        help="guided setup of environment for SUT (generate mitmproxy addons, build SUT)")
    parser.add_argument("--learner-setup", action="store_true",
                        help="guided setup of environment for statelearner (fetch and build statelearner)")
    parser.add_argument("--pre-startup", action="store_true",
                        help="guided startup of environment for SUT (usually just starts rabbitmq)")
    parser.add_argument("--statelearner", action="store_true",
                        help="start statelearner")
    args = parser.parse_args()

    # args that don't need config
    if args.install:
        guided_install()
        return 0
    elif args.readme:
        instructions()
        return 0

    # logging
    if args.verbose:
        os.makedirs("logs", mode=0o766, exist_ok=True)
        logger.remove()
        log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | " \
                     "<bold>{level}</bold> | " \
                     "<cyan>{extra[func_entry_exit]}</cyan> - " \
                     "{message}"
        logger.add(sys.stderr, level="INFO", format=log_format, colorize=True)
        logger.add(f"logs/slime-{os.getpid()}.log", level="INFO", format=log_format)
        logger.bind(func_entry_exit=f"{__name__}").info(f"Starting SLIME with pid={os.getpid()} args={sys.argv}")
    else:
        logger.remove()

    # set cwd to be same directory as config
    assert os.path.isfile(args.config)
    cwd, config_file = os.path.split(args.config)
    starting_dir = os.getcwd()
    if cwd:  # could be empty if already in cwd, then chdir fails
        os.chdir(cwd)
        os.makedirs("logs", mode=0o755, exist_ok=True)

    # args that use config
    if args.setup:
        guided_setup(config_file)
        return 0
    elif args.learner_setup:
        statelearner_setup(config_file)
        return 0
    elif args.pre_startup:
        guided_pre_startup(config_file)
        return 0
    elif args.statelearner:
        start_statelearner(config_file)
        return 0
    else:
        from .slime import SLIME
        slime = SLIME(args, config_file, starting_dir)
        start_time = time.time()
        slime.learningLoop()
        end_time = time.time()
        print(f"Learning finished in {end_time - start_time:.2f} seconds")
        slime.endLearning()
        return 0


if __name__ == "__main__":
    sys.exit(main())

