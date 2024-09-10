import copy
import pickle
import re
import sys
import typing
from .utils import loguru_decorator, for_all_methods


@for_all_methods(loguru_decorator)
class MessageFuzzerData:
    def __init__(self) -> None:
        self.session_history = []
        self.plaid_msg = []
        # self.full_history = []  # WARNING: This is lost on resuming from a previous log

    def store_history(self, msg_out: dict, symbol: str, cmd: str):
        # TODO: add message header (not just body), and whatever else is part of it, will need to upgrade mitm addon (low priority, not sure how useful it is for these protocols, if there is any variance between this and if modifying them would trigger anything)
        self.session_history.append({
            "cmd": cmd,
            "message": msg_out["msg"],
            "cookies": msg_out["cookies"] if "cookies" in msg_out else [],
            "type": msg_out["type"],
            "symbol": symbol,
            "mitm_name": msg_out["mitm"],
            "msg_mod": None
        })

    def get_plaid_msg(self) -> str:
        """returns an 'equivalent message string' to see if queries are effectively equivalent without knowing the state machine"""
        return "###".join(self.plaid_msg)

    def new_session(self):
        pickle.dump(self.session_history, self.pickle_file)
        self.pickle_file.flush()
        # self.full_history.append(copy.copy(self.session_history)) # deprecate, (could be nondeterminstic since a newer session could have different results at different times for the same query)
        self.session_history.clear()
        self.plaid_msg.clear()

    def open_log(self, resume: bool = False):
        if resume:
            self.pickle_file = open("logs/fuzzer.pickle", "ab")
        else:
            self.pickle_file = open("logs/fuzzer.pickle", "wb")

    def close_log(self):
        self.new_session()
        self.pickle_file.close()

@for_all_methods(loguru_decorator)
class MessageFuzzer:
    """base class"""
    def __init__(self, data: MessageFuzzerData) -> None:
        self.data = data
        self.session_history = data.session_history
        # self.full_history = data.full_history

    def _search_history(self, start: int = 0, stop: int = -1, most_recent:bool = True, type: str = None, symbol: str = None) -> int:
        """return a previous message matching some criteria, useful for different types of replays"""
        assert start >= 0 and stop <= 0
        search_range = range(start, len(self.session_history) + stop)
        if most_recent:
            search_range = reversed(search_range)
        for i in search_range:
            if type is not None and type != self.session_history[i]["type"]:
                continue
            if symbol is not None and symbol != self.session_history[i]["symbol"]:
                continue
            return i
        return None

    def _trailing_int(self, s: str) -> int:
        """return trailing integer of a string, default to 1 if no trailing integer"""
        m = re.search(r'\d+$', s)
        return int(m.group()) if m else 1

    def fuzz(self, cmd) -> tuple[int, str, dict]:
        output_return_code, replace_flag, new_cmd, extras = self.fuzzer(cmd)
        if new_cmd is None:
            # same command, no changes
            return output_return_code, cmd, extras
        if replace_flag:
            # replace message with modified version
            self.session_history[-1]["msg_mod"] = new_cmd
            if "cookies" in extras:
                self.session_history[-1]["cookies"] = extras["cookies"]
            new_cmd = "replace:" + new_cmd  # TODO, store new_cmd in extras["msg"] and use "replace" as cmd, this could simplify def fuzzer() by a lot as well and get rid of replace_flag
        # issueing a new command or message replacement
        return output_return_code, new_cmd, extras

    def fuzzer(self, cmd: str) -> typing.Tuple[int, bool, str, dict]:
        raise NotImplementedError

@for_all_methods(loguru_decorator)
class simple_fuzzer(MessageFuzzer):
    def fuzzer(self, cmd: str) -> tuple:
        # This class uses the return code as binary with the bits as follows:
        # bits: 2^2 2^1 2^0
        #        |   |   |__ 0 = success in completing action, 1 action not applicable to message
        #        |   |______ 0 = success in completing action, 1 have to wait for next message (response) to see if applicable
        #        |__________ 0 = success in completing action, 1 by coincidence, successful action resulted in the exact same message anyways 
        # how the return code is used is entirely fuzzer class dependent and can be used to indicate whatever makes sense
        # overall return code = request return code + response return code
        # if speed_optimizations are enabled, a non-zero overall return code results in session termination
        return_code = 0  # fuzz success
        replace_flag = False
        extras = {} # any extra info for msg_out: dict, eg old msg/cookie, depends on cmd
        plaid_msg = cmd  # commands and therefore plaid messages are distinct not assumed to be equivalent, can be updated for specific cases to reduce effectively equivalent options that don't need to be queried twice
        if cmd == "replacereq":
            if self.session_history[-1]["type"] == "request":
                replace_flag = True
                msg_out = re.sub("<int>\d+</int>", "<int>117</int>", self.session_history[-1]["message"])
                if "<int>117</int>" not in msg_out:
                    return_code = 1  # replace not success
            else:
                msg_out = "allow"
        elif cmd.startswith("replayreq"):
            """will replay whatever the last previous message was intended to be (even if it was replaced, modified, or killed)"""
            if self.session_history[-1]["type"] == "request":
                stop = -2 * self._trailing_int(cmd) + 1
                i = self._search_history(type="request", stop=stop)
                if i is not None:
                    replace_flag = True
                    msg_out = self.session_history[i]["message"]
                    plaid_msg = "%s#%s#%s" % ("replayreq", i, "msg")
                    extras["cookies"] = self.session_history[i]["cookies"]
                else:
                    return_code = 1
                    msg_out = "allow"
            else:
                msg_out = "allow"
                plaid_msg = "replayed"
        elif cmd.startswith("replayres"):
            """will replay whatever the last previous message was intended to be (even if it was replaced, modified, or killed)"""
            if self.session_history[-1]["type"] == "response":
                stop = -2 * self._trailing_int(cmd) + 1
                i = self._search_history(type="response", stop=stop)
                if i is not None:
                    replace_flag = True
                    return_code = -2
                    msg_out = self.session_history[i]["message"]
                    plaid_msg = "%s#%s#%s" % ("replayres", i, "msg")
                else:
                    return_code = 1
                    msg_out = "allow"
            else:
                return_code = 2
                msg_out = "allow"
                plaid_msg = "pending"
        elif cmd == "replayboth":
            # todo
            raise NotImplementedError
        elif cmd.startswith("realreplayreq"):
            """realreplay which will replay the actual previous message, even if it was modified, not what it was supposed to be"""
            if self.session_history[-1]["type"] == "request":
                stop = -2 * self._trailing_int(cmd) + 1
                i = self._search_history(type="request", stop=stop)
                if i is not None:
                    replace_flag = True
                    msg_out = self.session_history[i]["message"]
                    plaid_msg = "%s#%s#%s" % ("replayreq", i, "msg")
                    if self.session_history[i]["msg_mod"] is not None:
                        msg_out = self.session_history[i]["msg_mod"]
                        plaid_msg = "%s#%s#%s" % ("replayreq", i, "mod")
                    extras["cookies"] = self.session_history[i]["cookies"]
                else:
                    return_code = 1
                    msg_out = "allow"
            else:
                msg_out = "allow"
                plaid_msg = "replayed"
        elif cmd.startswith("realreplayres"):
            """realreplay which will replay the actual previous message, even if it was modified, not what it was supposed to be"""
            if self.session_history[-1]["type"] == "response":
                stop = -2 * self._trailing_int(cmd) + 1
                i = self._search_history(type="response", stop=stop)
                if i is not None:
                    replace_flag = True
                    return_code = -2
                    msg_out = self.session_history[i]["message"]
                    plaid_msg = "%s#%s#%s" % ("replayres", i, "msg")
                    if self.session_history[i]["msg_mod"] is not None:
                        msg_out = self.session_history[i]["msg_mod"]
                        plaid_msg = "%s#%s#%s" % ("replayres", i, "mod")
                else:
                    return_code = 1
                    msg_out = "allow"
            else:
                return_code = 2
                msg_out = "allow"
                plaid_msg = "pending"
        elif cmd == "smartreplayreq":
            """will replay the last message of the same type, if there is one"""
            if self.session_history[-1]["type"] == "request":
                i = self._search_history(symbol=self.session_history[-1]["symbol"], type="request")
                if i is not None:
                    replace_flag = True
                    msg_out = self.session_history[i]["message"]
                    plaid_msg = "%s#%s#%s" % ("replayreq", i, "msg")
                    extras["cookies"] = self.session_history[i]["cookies"]
                else:
                    return_code = 1
                    msg_out = "allow"
            else:
                msg_out = "allow"
                plaid_msg = "replayed"
        elif cmd == "smartreplayres":
            """will replay the last message of the same type, if there is one"""
            if self.session_history[-1]["type"] == "response":
                i = self._search_history(symbol=self.session_history[-1]["symbol"])
                if i is not None:
                    replace_flag = True
                    return_code = -2
                    msg_out = self.session_history[i]["message"]
                    plaid_msg = "%s#%s#%s" % ("replayres", i, "msg")
                else:
                    return_code = 1
                    msg_out = "allow"
            else:
                return_code = 2
                msg_out = "allow"
                plaid_msg = "pending"
        elif cmd == "spamreq":
            if self.session_history[-1]["type"] == "request":
                replace_flag = True
                msg_out = "spam"
            else:
                msg_out = "allow"
        elif cmd == "spamres":
            if self.session_history[-1]["type"] == "response":
                replace_flag = True
                return_code = -2
                msg_out = "spam"
            else:
                return_code = 2
                msg_out = "allow"
        elif cmd == "blankreq":
            if self.session_history[-1]["type"] == "request":
                replace_flag = True
                msg_out = ""
            else:
                msg_out = "allow"
        elif cmd == "blankres":
            if self.session_history[-1]["type"] == "response":
                replace_flag = True
                return_code = -2
                msg_out = ""
            else:
                return_code = 2
                msg_out = "allow"
        elif cmd == "blankboth":
            replace_flag = True
            msg_out = ""
        else:
            self.data.plaid_msg.append(plaid_msg)
            return return_code, replace_flag, None, extras
        # need to update later (just a speed optimization so low priority), eg message may be the same still but cookie changed
        # if msg_out == self.session_history[-1]["message"]:
        #     # by coincidence the modification ends up being exactly the same as what it was supposed to be
        #     return_code += 4
        self.data.plaid_msg.append(plaid_msg)
        return return_code, replace_flag, msg_out, extras

class no_fuzz(MessageFuzzer):
    @loguru_decorator
    def fuzzer(self, cmd: str) -> tuple:
        return 0, False, None

@loguru_decorator
def select_msgfuzzer(data: MessageFuzzerData, fuzzer: str = "simple_fuzzer", user_module = None) -> MessageFuzzer:
    if user_module and hasattr(user_module, fuzzer):
        return getattr(user_module, fuzzer)(data)
    else:
        return getattr(sys.modules[__name__], fuzzer)(data)
