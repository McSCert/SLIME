# Standard library
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
import re
import site
import importlib
# Third party
import psutil
# Local
from .msgbroker import FakeSocketClient, QuickSocketServer, Bugs
from .utils import readJson, LearnlibCommandLog, terminator, loguru_decorator
from .sutctrl import start_sutctrl
from .sutman import SutManager
from .mitmproxyctrl import start_mitm
from .mitmman import MitmManager



class SLIME:
    @loguru_decorator
    def __init__(self, args, config_file, starting_dir):
        self.config = readJson(config_file)
        self.args = args
        self.learning_session_locals = {}

        # import user module (can be used by msg_parser, msg_fuzzer, controller_class)
        if self.config["slime_config"]["custom_module"]:
            # make sure the path of the custom module is in the python path
            site.addsitedir(os.path.split(os.path.abspath(self.config["slime_config"]["custom_module"]))[0])
            # import the custom module, removes the .py extension and anchor package for relative imports
            user_module = importlib.import_module(self.config["slime_config"]["custom_module"].rstrip(".py"), package=__package__)
        else:
            user_module = None

        # startup system under test controller
        if args.s is not None or args.ss:
            if os.getuid() != 0:
                print("Warning: SLIME is about to start a SUT without root privileges")
                print("If the SUT requires root privileges, it is recommended to grant them now")
                grant_root = input("Give SLIME root privileges now (y/N)? ")
                if grant_root.startswith("y"):
                    if os.getcwd() != starting_dir:
                        os.chdir(starting_dir)
                    args = ["sudo", "-E", "python3", "-m", "slime", *sys.argv[1:]]
                    os.execvp("sudo", args)
            if args.ss:
                sut_name = args.ss
            else:
                sut_name = list(self.config["sut_controllers"].keys())[args.s]
            print("STARTING SUT: " + sut_name)
            start_sutctrl(self.config["sut_controllers"][sut_name], sut_name, user_module)
            sys.exit()      

        # init mitm controller
        self.mitm = MitmManager(self.config, user_module)

        # startup mitm servers
        if args.m is not None or args.mm:
            # select mitm from config
            if args.mm:
                mitm_name = args.mm
                args.m = list(self.config["mitm_controllers"].keys()).index(mitm_name)
            else:
                mitm_name = list(self.config["mitm_controllers"].keys())[args.m]
            # switch to mitmweb if interactive
            if args.i and "mitm_interactive_web_port" in self.config["slime_config"] and type(self.config["slime_config"]["mitm_interactive_web_port"]) == int:
                cmd_start = self.config["mitm_controllers"][mitm_name]["cmd_start"]
                cmd_start = cmd_start.replace("mitmdump", "mitmweb --web-port " + str(self.config["slime_config"]["mitm_interactive_web_port"] + args.m))
                self.config["mitm_controllers"][mitm_name]["cmd_start"] = cmd_start
            print("STARTING MITM: " + mitm_name)
            start_mitm(self.config["mitm_controllers"][mitm_name]) # this runs forever now and need to rerun slime.py in a new terminal
            if args.i:
                code.interact(local=locals())
            sys.exit() # don't want to run again and accidentally overwrite anything

        # clean up proc if I have root then exit, only run without root otherwise uptane dir needs cleaning
        if args.f:
            terminator([self.config["slime_config"]["statelearner_port"]])
            self.mitm.clearFlows()
            # todo: add cleanup command to config to reset iptables
            # stop all running containers
            self.sut = SutManager(self.config["sut_controllers"], user_module)
            for i in range(self.sut.len()):
                self.sut.q(i).send("KILL")
            time.sleep(2)
            self.mitm.clearFlows()
            sys.exit()

        # having root messes up permissions of temp/cached files
        # move this to top if args.f can ask for root after running
        if os.getuid() == 0:
            sys.exit()

        # init logging
        self.log = LearnlibCommandLog(resume=args.r, ludicrous_speed=self.config["slime_config"]["ludicrous_speed"], plaid=self.config["slime_config"]["plaid"])
        self.mitm.fuzzer_data.open_log(resume=args.r)

        # setup socket to statelearner
        print("Connecting to statelearner...")
        if args.l or args.r:
            self.ll = QuickSocketServer(self.config["slime_config"]["statelearner_port"])
        elif args.c:
            self.ll = FakeSocketClient()
        else:
            print("Error, no mode selected, run with --help to see available options")
            sys.exit(1)
        print("Connected")

        # load alphabet symbols (for learning the same system under different conditions, so symbols are in the same order, can also use consistentlabeler for this)
        if args.a:
            self.mitm.parser_data.readSymbols()

        # resume previous session
        if args.r:
            self.mitm.parser_data.readSymbols()
            print("Replaying previous queries")
            replay_count = 0
            cache_count = 0
            while True:
                # load previous query
                query, response = self.log.resume_next()
                if query and response:
                    new_query = self.ll.listen()
                    if query == new_query:
                        # learning session has remained the same so far (this should be the case unless statelearner.properties has been changed)
                        print ("input query: " + query)
                        print ("res: " + response)
                        replay_count += 1
                        self.log.write_entry(True)
                        self.ll.send(response)
                    else:
                        # resumed as much as possible, put next query into a stack and load remaining entries to cache
                        print("Caching remaining previous queries")
                        self.ll.push(new_query)
                        while query and response:
                            cache_count += 1
                            self.log.write_entry(False)
                            query, response = self.log.resume_next()     
                else:
                    break
            print("Loaded %s queries, of which %s were replayed and %s were only cached" % (replay_count+cache_count, replay_count, cache_count))

        # setup systems under test
        print("Setting up systems under test...")
        self.sut = SutManager(self.config["sut_controllers"], user_module)

    @loguru_decorator
    def killSuts(self):
        self.mitm.clearFlows() # clean up any flows that are waiting, easier to kill SUTs that aren't hanging in the middle of a flow
        for i in range(self.sut.len()):
            self.sut.q(i).send("KILL") # remember where clean slate is, i had a reason to do it before kill, and after killing, don't know where it should be now
            _ = self.sut.q(i).listen()
        time.sleep(0.1) # is 2 always enough? more or less???

    @loguru_decorator
    def startSuts(self):
        self.mitm.clearQueues() # clear queues before restarting SUTs
        time.sleep(0.2)
        for i in range(self.sut.len()):
            self.sut.q(i).send("START")
            _ = self.sut.q(i).listen()
        self.mitm.reset() # starts by listening for the first request

    # @pysnooper.snoop('logs/pysnooper.log')
    @loguru_decorator
    def learningSession(self, input_query: str) -> tuple[str, str]:
        # split string of commands into list (deliminator defined in stateleaner socket.properties)
        input_symbols = input_query.split(";")
        output_symbols = []
        state_coverage = []
        query_timestamps = []
        if "enable_preseed" in self.config["slime_config"] and self.config["slime_config"]["enable_preseed"]:
            input_symbols = self.config["slime_config"]["preseed"] + input_symbols
        len_input_symbols = len(input_symbols)
        if self.args.i:
            self.config["slime_config"]["ludicrous_speed"] = False
            len_input_symbols = 9000 # lazy hack so interactive mode doesn't stop early, no one would go over 9000
        query_timestamps.append(time.time())
        for cmd_index in range(-1, len_input_symbols):
            # start at -1 and increment at start of loop
            # select command with support for interactive mode
            cmd_index += 1
            cmd = "DONE"
            if cmd_index < len(input_symbols):
                cmd = input_symbols[cmd_index]
            # select command if interactive mode
            if self.args.i:
                cmd_options = ["DONE", cmd] + self.config["slime_config"]["mitm_interactive_input_alphabet"]
                print("Enter number to select command or input manually:")
                for i, c in enumerate(cmd_options):
                    print(str(i) + ": " + c)
                cmd_next = input(">>> ")
                if cmd_next.isdigit():
                    cmd = cmd_options[int(cmd_next)]
                else:
                    cmd = cmd_next
            if cmd == "DONE":
                break
            # error until proven otherwise
            response = "ERROR"
            if cmd == None or cmd == [] or cmd == "":
                raise ValueError("given empty cmd")
            # parse cmd symbol
            cmd = cmd.split("-")
            try:
                input_type = cmd[0]
                if len(cmd) == 4:
                    assert input_type in ["m", "s"]
                    target = cmd[1]
                elif len(cmd) == 3:
                    assert input_type in ["m"]
                    target = None
                else:
                    raise Exception()
                action = cmd[-2]
                output_type = cmd[-1]
                assert output_type in ["rr"]
            except Exception:
                raise ValueError("cmd not specified properly")
            ## return_source = cmd[4]
            # get code coverage at current state before cmd/mitm action
            state_coverage.append(self.sut.get_traces())
            # send command to SUT if provided
            if input_type == "s":
                pass
                # TODO
                # Might want to grab coverage here again
            # send command to mitm if provided (first available if no name provided, TODO (maybe): select specific mitm)
            elif input_type == "m":
                response = self.mitm.process_action(action)
            # select the correct return source for the output alphabet symbol
            # TODO: use a dict for response (rename) with request, response
            output_symbols.append(response)
            query_timestamps.append(time.time())
            if self.args.i:
                print("output: " + response)
            if self.config["slime_config"]["ludicrous_speed"] and response in ["term", "noflow"]:
                while len(output_symbols) < len(input_symbols):
                    output_symbols.append(response)
                break
            if self.config["slime_config"]["ludicrous_speed"] and response.split("-")[-1] == "null":
                # TODO Create flag for null request terminates as noflow
                while len(output_symbols) < len(input_symbols):
                    output_symbols.append("noflow")
                break

        # finished testing query
        if output_symbols == []:
            # something weird happened or LL is done?
            raise Exception("empty list of output symbols")
        else:
            # remove responses from preseeded queries so length of output_symbols matches input_symbols for learnlib
            if "enable_preseed" in self.config["slime_config"] and self.config["slime_config"]["enable_preseed"]:
                output_symbols = output_symbols[len(self.config["slime_config"]["preseed"]):]
                query_timestamps = query_timestamps[len(self.config["slime_config"]["preseed"]):]
            query_response = ";".join(output_symbols)
        # also need coverage at the end of each session
        state_coverage.append(self.sut.get_traces())

        # convert time to time diff strings
        query_timediffs = [str(query_timestamps[i+1] - query_timestamps[i]) for i in range(len(query_timestamps)-1)]
        query_timediffs = ";".join(query_timediffs)

        # log traces, locals for debugging, and return response
        self.log.update_entry("plaid_msg", self.mitm.fuzzer_data.get_plaid_msg())
        self.log.update_entry("traces", state_coverage)
        self.learning_session_locals = locals()
        return query_response, query_timediffs

    @loguru_decorator
    def learningLoop(self):
        try:
            if self.args.n:
                raise Exception("No run")
            use_mitm_process_ctrl = False
            mitm_process_ctrl = Bugs("mitm_process_ctrl", False)
            for mitm in self.config["mitm_controllers"]:
                if "restart_between_sessions" in self.config["mitm_controllers"][mitm] and self.config["mitm_controllers"][mitm]["restart_between_sessions"]:
                    assert not use_mitm_process_ctrl, "Only one mitm can be set to restart between sessions"
                    use_mitm_process_ctrl = True
            print("Starting learning loop")
            while True:
                # better to stop and resume later if memory leak than ruin results with non-deterministic timeouts
                assert psutil.virtual_memory().percent < 90
                assert psutil.disk_usage(os.getcwd()).percent < 99
                while psutil.cpu_percent() > 90:
                    time.sleep(1)
                lookup_query = True
                if self.args.i:
                    print("Get next (q)uery, Only use (c)ustom commands, (s)top:")
                    next_query = input(">>> ")
                    if next_query.lower().startswith("q"):
                        input_query = self.ll.listen()
                    elif next_query.lower().startswith("c"):
                        input_query = "DONE"
                        lookup_query = False
                    else:
                        input_query = None
                else:
                    input_query = self.ll.listen()
                if not input_query:
                    raise EOFError("cmd list is empty")
                print("\033[92mstarting learning session - \033[0m" + time.ctime())
                print("\033[92minput query:\033[0m " + input_query)
                self.log.new_entry()
                self.log.update_entry("query", input_query)
                if lookup_query:
                    query_response = self.log.lookup_query(input_query)
                else:
                    query_response = None
                if query_response is None:
                    print("\033[93mquerying sut(s)\033[0m")
                    if use_mitm_process_ctrl:
                        self.mitm.clearQueues()
                        mitm_process_ctrl.send("start")
                        mitm_process_ctrl.listen()
                    self.startSuts()
                    query_response, query_timediffs = self.learningSession(input_query)
                    self.killSuts()  # might be better before where log was written before restarting sut, but if they fail to restart, maybe session had an issue and response discarded
                    if use_mitm_process_ctrl:
                        mitm_process_ctrl.send("stop")
                        mitm_process_ctrl.listen()
                        self.mitm.clearQueues()
                else:
                    query_timediffs = ""
                    print("\033[94mfound matching query in cache\033[0m")
                print("\033[92mres:\033[0m " + str(query_response))
                self.log.update_entry("response", query_response)
                self.log.update_entry("transition_times", query_timediffs)
                self.log.write_entry(True)
                self.ll.send(query_response)
                print("\033[92mupdated log and sent response\033[0m")

        except Exception as e:
            print(e.args)
            traceback.print_stack()
            traceback.print_exc()
            # traceback.print_tb(e.__traceback__)
            # print(sys.exc_info()[2])
            # pdb.set_trace()

        except KeyboardInterrupt:
            print("KEYBOARD INTERRUPT")
            traceback.print_stack()
            traceback.print_exc()
            # alternate implementation
            # def signal_handler(signal, frame):
            #     print 'You pressed Ctrl+C - or killed me with -2'
            #     sys.exit(0)
            # signal.signal(signal.SIGINT, signal_handler)
            # print 'Press Ctrl+C'
            # signal.pause()

    @loguru_decorator
    def writeLogs(self):
        self.log.write_entry("unknown")
        self.log.close()
        self.mitm.parser_data.writeSymbols()
        self.mitm.parser_data.writeParserErrors()
        self.mitm.fuzzer_data.close_log()

    @loguru_decorator
    def endLearning(self):
        self.writeLogs()
        self.ll.close()
        environment = {}
        environment.update(globals())
        environment.update(locals())
        environment.update(self.learning_session_locals)
        code.interact(local=environment)


