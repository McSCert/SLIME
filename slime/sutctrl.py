# Standard library
import os
import importlib
import itertools
import multiprocessing
import queue
import pickle
import re
import shutil
import subprocess
import shlex
import sys
import time
# Third party
import psutil
# Local
from .utils import loguru_decorator, for_all_methods
from .msgbroker import Bugs


@for_all_methods(loguru_decorator)
class SUTController:
    """base class"""
    def __init__(self, config: dict, name: str) ->  None:
        self.config = config
        self.name = name

    def run(self) -> None:
        raise NotImplementedError

    def kill(self) -> None:
        raise NotImplementedError

    def trace(self) -> str:
        raise NotImplementedError

    def stdout(self) -> str:
        raise NotImplementedError

    def stdin(self, input: str) -> None:
        raise NotImplementedError

    def checkpoint(self) -> None:
        raise NotImplementedError

    def restore(self) -> None:
        raise NotImplementedError


@for_all_methods(loguru_decorator)
class Simple_Ready_SUT(SUTController):
    """Simple SUT that is ready (to bring up the next SUT or start learning) when a string is printed to stdout via cmd_ready, also requires cmd_start and cmd_stop"""
    def run(self):
        subprocess.run(shlex.split(self.config["cmd_start"]))
        if "cmd_ready" in self.config and self.config["cmd_ready"]:
            while "ready" not in subprocess.run(shlex.split(self.config["cmd_ready"]), capture_output=True, universal_newlines=True).stdout:
                time.sleep(0.2)

    def kill(self):
        subprocess.run(shlex.split(self.config["cmd_stop"]))



@for_all_methods(loguru_decorator)
class Simple_Client_SUT(Simple_Ready_SUT):
    """Simple SUT that is ready immediately, and requires cmd_start and cmd_stop"""
    def run(self):
        subprocess.Popen(shlex.split(self.config["cmd_start"]))


@for_all_methods(loguru_decorator)
class Simple_Server_SUT(Simple_Ready_SUT):
    """Simple SUT that is ready when bound to listen_port, or any port if not specified, requires cmd_start and cmd_stop"""
    def run(self):
        proc = subprocess.Popen(shlex.split(self.config["cmd_start"]))
        self.proc = psutil.Process(proc.pid)
        if "listen_port" in self.config:
            while not any(c.laddr.port == self.config["listen_port"] for c in psutil.net_connections() if c.status == "LISTEN"):
                time.sleep(0.1)
        else:
            while not (any(p.connections() for p in self.proc.children(recursive=True)) or self.proc.connections()):
                time.sleep(0.1)


@for_all_methods(loguru_decorator)
class Simple_Kill_Client_SUT(SUTController):
    """Simple SUT that is ready immediately, requires only cmd_start (kill is handled by SUTController)"""
    def run(self):
        self.p = subprocess.Popen(shlex.split(self.config["cmd_start"]))
        self.proc = psutil.Process(self.p.pid)

    def kill(self):
        # kill process and all children, and make sure they are dead
        for child in self.proc.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        try:
            self.proc.kill()
        except psutil.NoSuchProcess:
            pass
        while self.proc.is_running():
            try:
                self.proc.kill()
            except psutil.NoSuchProcess:
                break


@for_all_methods(loguru_decorator)
class Simple_Kill_Server_SUT(Simple_Kill_Client_SUT, Simple_Server_SUT):
    """Simple SUT that is ready when bound to listen_port, or any port if not specified, requires only cmd_start (kill is handled by SUTController)"""
    def run(self):
        Simple_Server_SUT.run(self)

    def kill(self):
        Simple_Kill_Client_SUT.kill(self)


@for_all_methods(loguru_decorator)
class Simple_Root_Client_SUT(Simple_Kill_Client_SUT):
    """Like Simple_Kill_Client_SUT but runs as root, and runs cmd_start in a subprocess with sudo -i -u $SUDO_USER"""
    def run(self):
        args = ["sudo", "-i", "-u", os.getenv('SUDO_USER'), "bash", "-c", f"cd \"{os.getcwd()}\";{self.config['cmd_start']} & echo $! > slime-{self.name}.pid"]
        subprocess.Popen(args)
        for _ in range(10):
            if os.path.exists(f"slime-{self.name}.pid"):
                break
            time.sleep(0.1)
        with open(f"slime-{self.name}.pid", "r") as f:
            self.pid = int(f.read())
        os.remove(f"slime-{self.name}.pid")
        self.proc = psutil.Process(self.pid)


@for_all_methods(loguru_decorator)
class Simple_Root_Server_SUT(Simple_Kill_Client_SUT):
    """Like Simple_Kill_Server_SUT but runs as root, and runs cmd_start in a subprocess with sudo -i -u $SUDO_USER"""
    def run(self):
        super().run()
        if "listen_port" in self.config:
            while not any(c.laddr.port == self.config["listen_port"] for c in psutil.net_connections() if c.status == "LISTEN"):
                time.sleep(0.1)
        else:
            while not (any(p.connections() for p in self.proc.children(recursive=True)) or self.proc.connections()):
                time.sleep(0.1)


class SUT_uflow(SUTController):
    """SUT for uflow, requires (warning, code is pretty bad and getting this working was quite finicky, documentation may be slightly off but the example works):
    cmd_startup is run before the SUT is started and must terminate    (don't confuse with cmd_start, these are not the same!)
    cmd_run is run in the background to start the SUT                  (don't confuse with cmd_start, these are not the same!)
    cmd_pid is run to get the PID of the SUT, if not specified, the PID is assumed to be printed to stdout by cmd_run
    cmd_ready is run to check if the SUT is ready, if not specified, the SUT is assumed to be ready immediately
    cmd_stop is run to stop the SUT
    cmd_uflow is run to get a trace of the SUT, and must print the trace to stdout
    trace_filter is a regex to filter include in the trace, and trace_filter_exclude is a list of regex to exclude lines from the trace
    """
    @loguru_decorator
    def __init__(self, config: dict, name: str) -> None:
        super().__init__(config, name)
        self.trace_filter = re.compile(config["trace_filter"])
        if "trace_filter_exclude" in config:
            self.trace_filter_exclude = re.compile(config["trace_filter_exclude"])

    @loguru_decorator
    def run(self):
        if "cmd_startup" in self.config and self.config["cmd_startup"]:
            subprocess.run(shlex.split(self.config["cmd_startup"]))
            time.sleep(0.5)
        self.client = subprocess.Popen(shlex.split(self.config["cmd_run"]), stdout=subprocess.PIPE, universal_newlines=True)
        time.sleep(0.5)
        print("PID")
        if "cmd_pid" in self.config:
            pid = subprocess.run(shlex.split(self.config["cmd_pid"]), capture_output=True, universal_newlines=True).stdout
        else:
            pid = str(int(self.client.stdout.read().strip()))
        self.tmp_pid = pid  # try killing processes that have uflow and this pid in the command line to get rid of zombies
        print(pid)
        self.tracer = subprocess.Popen(shlex.split(self.config["cmd_uflow"]) + [pid], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
        self.q_trace = multiprocessing.Queue()
        self.p_trace = multiprocessing.Process(name="tracer", target=self._tracer, args=(self.tracer, self.q_trace))
        self.p_trace.start()
        if "cmd_ready" in self.config and self.config["cmd_ready"]:
            while "ready" not in subprocess.run(shlex.split(self.config["cmd_ready"]), capture_output=True, universal_newlines=True).stdout:
                time.sleep(0.5)
        # time.sleep(1)
        # subprocess.run(shlex.split(self.config["cmd_is_ready"]))

    @loguru_decorator
    def kill(self):
        # todo: make this more robust (check if killed, do async to improve performance, etc)
        self.p_trace.terminate()
        self.p_trace.join(0.5)
        if self.p_trace.is_alive():
            self.p_trace.kill()
        self.p_trace.close()
        self.q_trace.close()
        self.tracer.stdout.close()
        self.tracer.terminate()
        try:
            self.tracer.wait(0.5)
        except subprocess.TimeoutExpired:
            self.tracer.kill()
        self.tracer.wait()
        del(self.tracer)
        self.client.stdout.close()
        self.client.terminate()
        try:
            self.client.wait(0.5)
        except subprocess.TimeoutExpired:
            self.client.kill()
        self.client.wait()
        del(self.client)
        for proc in psutil.process_iter(attrs=["name", "cmdline", "pid"], ad_value=""):
            proc = proc.info
            if "uflow" in proc["name"] and self.tmp_pid in proc["cmdline"]:
                proc = psutil.Process(proc["pid"])
                proc.terminate()
                try:
                    proc.wait(0.5)
                except psutil.TimeoutExpired:
                    proc.kill()
                break
        subprocess.run(shlex.split(self.config["cmd_stop"]))

    @loguru_decorator
    def trace(self):
        trace = ""
        try:
            time.sleep(0.1)
            trace += self.q_trace.get(timeout=1)
            trace += self.q_trace.get(timeout=0.1)
            trace += self.q_trace.get(timeout=0.1)
            while True:
                trace += self.q_trace.get(block=False)
        except queue.Empty:
            pass
        trace = "\n".join(filter(self.trace_filter.match, trace.splitlines()))
        if "trace_filter_exclude" in self.config:
            trace = "\n".join(itertools.filterfalse(self.trace_filter_exclude.match, trace.splitlines()))
        return trace

    @staticmethod
    def _tracer(proc, q):
        # for line in proc.stdout.readlines():
        #     q.put(line)
        for line in iter(proc.stdout.readline, ""):
            q.put(line.strip() + "\n")

@for_all_methods(loguru_decorator)
class SUT_uflow_no_tracing(Simple_Ready_SUT):
    """Compatible with uflow cmd options, but can be used when tracing is disabled for performance reasons"""
    def run(self):
        subprocess.run(shlex.split(self.config["cmd_startup"]))
        self.client = subprocess.Popen(shlex.split(self.config["cmd_run"]), stdout=subprocess.PIPE, universal_newlines=True)
        if "cmd_ready" in self.config and self.config["cmd_ready"]:
            while "ready" not in subprocess.run(shlex.split(self.config["cmd_ready"]), capture_output=True, universal_newlines=True).stdout:
                time.sleep(0.2)

    def kill(self):
        subprocess.run(shlex.split(self.config["cmd_stop"]))


class SUT_callgrind(SUTController):
    pass
    # TODO: create from aktualizr code


@loguru_decorator
def start_sutctrl(config: dict, name: str, user_module = None):
    q = Bugs(name, False)
    q.initQueues()
    # sut = Container2(config["container_type"], name, config["container_image"], config["startup_cmd"], config["trace_cmd"], config)
    if user_module and hasattr(user_module, config["controller_class"]):
        controller_class = getattr(user_module, config["controller_class"])
    else:
        controller_class = getattr(sys.modules[__name__], config["controller_class"])
        # could also use `controller_class = globals[config["controller_class"]]`, not sure which is more robust atm, or equivalent
        # https://stackoverflow.com/questions/990422/how-to-get-a-reference-to-current-modules-attributes-in-python
    # all of the options under controller_options are for the controller_class, and only the controller_class, which gets only these options and the SUT name
    sut = controller_class(config["controller_options"], name)
    while True:
        sut_cmd = q.listen().strip()
        if sut_cmd == "":
            # from initQueues
            continue
        elif sut_cmd == "KILL":
            print("killing")
            sut.kill()
            q.send("KILLED")
            print("killed")
        elif sut_cmd == "START":
            print("starting")
            sut.run()
            q.send("STARTED")
            print("started")
        elif sut_cmd == "GETTRACE":
            print("get trace")
            trace = sut.trace()
            q.send(trace)
            print("got trace")
        elif sut_cmd == "CHECKPOINT":
            print("saving checkpoint")
            sut.checkpoint()
            q.send("CHECKPOINT COMPLETE")
            print("checkpoint saved")
        elif sut_cmd == "RESTORE":
            print("restoring checkpoint")
            sut.checkpoint()
            q.send("RESTORE COMPLETE")
            print("checkpoint restored")
        elif sut_cmd == "STDOUT":
            print("get stdout")
            output = sut.stdout()
            q.send(output)
            print("got stdout")
        elif sut_cmd in config["sut_input_alphabet"]:
            # don't need to error check this since exception raised next anyways if not in here
            print(sut_cmd)
            sut.stdin(config["sut_input_alphabet"][sut_cmd])
            q.send("STDIN")
            print("send cmd")
        else:
            raise Exception(sut_cmd)
