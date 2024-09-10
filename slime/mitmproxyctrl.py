# Standard library
import subprocess
import shlex
import signal
import time
import os
import pickle
# Third party
import psutil
from mitmproxy import proxy, options
from mitmproxy.tools.dump import DumpMaster
from mitmproxy.addons import core
# Local
from .msgbroker import Bugs
from .utils import writeCsv, writeJson, loguru_decorator


@loguru_decorator
def start_mitm(config):
    if "restart_between_sessions" in config and config["restart_between_sessions"]:
        q = Bugs("mitm_process_ctrl", True)
        q.initQueues()
        q.clear()
        signal.signal(signal.SIGINT, lambda *args: q.requeue("terminate"))
        while True:
            msg = q.listen()
            if msg == "stop":
                p.send_signal(signal.SIGINT)
                p.wait()
                q.send("stopped")
            elif msg == "start":
                p = subprocess.Popen(shlex.split(config["cmd_start"]))
                while not psutil.Process(p.pid).connections():
                    time.sleep(0.1)
                q.send("started")
            elif msg == "terminate":
                p.send_signal(signal.SIGINT)
                p.wait()
                break
            else:
                raise Exception("Invalid message to mitm process: %s" % msg)
    else:
        subprocess.run(shlex.split(config["cmd_start"]))

class MitmCtrl:
    @loguru_decorator
    def __init__(self):
        self.q = Bugs("mitm", True)
        self.q.initQueues()
        self.q.clear()
        self.last_mitm = ""
        self.last_msg_type = ""

    @loguru_decorator
    def clearQueues(self):
        self.q.clear()

    @loguru_decorator
    def clearFlows(self):
        msg_out = {
            "type": "clear_flows"
        }
        self.q.send(pickle.dumps(msg_out, 0).decode())
        # if self.last_msg_type in ["request"]:
        #     while self.q.listen() != "ack_clear_flows":
        #         pass

    @loguru_decorator
    def send(self, cmd: str, extras: dict):
        """create input message for mitmproxyaddon from cmd"""
        self.q.clear()
        msg_in = {
            "type": "cmd",
            "mitm": self.last_mitm
        }
        if self.last_msg_type in ["request", "timeout"]:
            if cmd == "killreq":
                msg_in["msg"] = "killreq"
                # might be too late, might need to kill at connect, not sure if "HTTP request headers were successfully read." means read by mitmproxy or by server, assuming former
            elif cmd == "killres":
                msg_in["msg"] = "allowreq"
                # same comment as request
            elif cmd == "lowergetreq":
                msg_in["msg"] = "lowergetreq"
            elif cmd == "allow" or cmd == "allowreq":
                msg_in["msg"] = "allowreq"
            elif cmd.startswith("replace:"):
                msg_in["msg"] = "replacereq"
                msg_in["msg+"] = cmd[8:]
                if "cookies" in extras:
                    msg_in["cookies"] = extras["cookies"]
            else:
                raise Exception("Invalid command for mitm: %s" % cmd)
        elif self.last_msg_type == "response":
            if cmd == "killres":
                msg_in["msg"] = "killres"
                # same comment as request
            elif cmd == "lowergetreq":
                msg_in["msg"] = "allowres"
            elif cmd == "allow" or cmd == "allowres":
                msg_in["msg"] = "allowres"
            elif cmd.startswith("replace:"):
                msg_in["msg"] = "replaceres"
                msg_in["msg+"] = cmd[8:]
            else:
                raise Exception("Invalid command for mitm: %s" % cmd)
        # elif self.last_msg_type == "timeout":
        #     msg_in["msg"] = "unknown"  # this will cause an error if the SUT wakes up, otherwise it is harmless for completing the current session
        self.q.send(pickle.dumps(msg_in, 0).decode())

    @loguru_decorator
    def listen(self, timeout = None) -> dict:
        """get output message from mitmproxyaddon"""
        msg_out = self.q.listen(timeout)
        self.q.clear()
        if msg_out in ["TIMEOUT", "ERROR"]:
            # likely to be noflow for the rest of the current session (since no REQUEST or response in queue)
            # responses can be skipped/null, but that won't cause a timeout because listen would grab the next request, that being null would need a SUT input command to restart 
            self.last_msg_type = msg_out.lower()
            msg_out = {
                "type": self.last_msg_type,
                "mitm": None,
                "msg": "MITM_" + msg_out
            }
        else:
            msg_out = pickle.loads(msg_out.encode())
            self.last_mitm = msg_out["mitm"]
            self.last_msg_type = msg_out["type"]
        return msg_out

    @loguru_decorator
    def getQLog(self):
        # need to uncomment code for logAppend in msgbroker
        return self.q.getLog()

    @loguru_decorator
    def writeQLog(self, time = False):
        self.q.writeLog()
