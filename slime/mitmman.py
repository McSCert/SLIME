from .utils import loguru_decorator
from .msgbroker import Bugs
from .mitmproxyctrl import MitmCtrl
from .msgparser import MessageParserData, select_msgparser
from .msgfuzzer import MessageFuzzerData, select_msgfuzzer

class MitmManager:
    # todo: combine with mitmproxyctrl
    @loguru_decorator
    def __init__(self, config:dict, user_module = None):
        self.config = config
        self.controller = MitmCtrl()
        self.parsers = {}
        self.parser_data = MessageParserData()
        self.fuzzers = {}
        self.fuzzer_data = MessageFuzzerData()
        self.last_mitm = ""
        self.timeout = config["slime_config"]["mitm_timeout"]
        self.ludicrous_speed = config["slime_config"]["ludicrous_speed"]
        for mitm_name in config["mitm_controllers"]:
            self.parsers[mitm_name] = select_msgparser(self.parser_data, config["mitm_controllers"][mitm_name]["msg_parser"], user_module)
            self.fuzzers[mitm_name] = select_msgfuzzer(self.fuzzer_data, config["mitm_controllers"][mitm_name]["msg_fuzzer"], user_module)

    @loguru_decorator
    def clearFlows(self):
        self.controller.clearFlows()

    @loguru_decorator
    def clearQueues(self):
        self.controller.clearQueues()

    @loguru_decorator
    def reset(self):
        # never need the first "response" (gotta refactor that), since it will be the first request, then learning either from the response or request after the first action
        # should be the json msg_out (want to raise the exception if it's not)
        # could be nothing if using sut_cmd in the alphabet (implement flag for this later)
        self.timeout = self.config["slime_config"]["mitm_timeout"]
        self.fuzzer_data.new_session()
        msg_out = self.controller.listen(self.timeout)  # WARNING, if this times out msg_out["mitm"] will be None, raising an exception in process_msg()
        self.process_msg(msg_out, "slime_session_reset")

    @loguru_decorator
    def fuzz(self, cmd: str) -> tuple:
        return self.fuzzers[self.last_mitm].fuzz(cmd)

    @loguru_decorator
    def query_mitm(self, cmd: str):
        flag, cmd, extras = self.fuzz(cmd)
        self.controller.send(cmd, extras)
        return flag, self.controller.listen(self.timeout)

    @loguru_decorator
    def process_msg(self, msg_out: dict, cmd: str):
        self.last_mitm = msg_out["mitm"]
        # TODO: make a config for each mitm, which components to parse, and provide as a dict to parser instead of str (logic for selecting field will be in parser config, not here, dict will just be msg_out)
        # if "path" in msg_out:
        #     msg = f"path={msg_out['path']} msg={msg_out['msg']}"
        # else:
        #     msg = msg_out["msg"]
        msg = msg_out["msg"]
        output_symbol = self.parsers[msg_out["mitm"]].parse(msg, msg_out["type"], msg_out["mitm"])
        self.fuzzer_data.store_history(msg_out, output_symbol, cmd)
        return output_symbol

    @loguru_decorator
    def process_action(self, cmd) -> str:
        flag, msg_out = self.query_mitm(cmd)
        output_return_code = flag  # default = 0 = action success
        output_symbol_response = "null"
        output_symbol_request = "null"
        if msg_out["type"] == "timeout":
            # likely to be noflow for the rest of the current session
            self.timeout = self.config["slime_config"]["noflow_timeout"]
            return "noflow"
        # elif msg_out["type"] == "error":
        #     # raise Exception("mitmproxy addon error")
        #     return "errorres"
        elif msg_out["type"] == "response" or msg_out["type"] == "error":
            if msg_out["type"] == "response":
                output_symbol_response = self.process_msg(msg_out, cmd)
            elif msg_out["type"] == "error":
                output_symbol_response = "proxyerror"
            flag, msg_out = self.query_mitm(cmd)
            output_return_code += flag
            if msg_out["type"] == "timeout":
                # may be likely to be noflow for the rest of the current session
                # self.timeout = self.config["slime_config"]["noflow_timeout"]
                output_symbol_request = "null"
            elif msg_out["type"] == "error":
                # raise Exception("mitmproxy addon error")
                output_symbol_request = "proxyerror"
            elif msg_out["type"] == "request":
                output_symbol_request = self.process_msg(msg_out, cmd)
            else:
                output_symbol_request = "msgerror"
        elif msg_out["type"] == "request":
            output_symbol_request = self.process_msg(msg_out, cmd)
        else:
            output_symbol_response = "msgerror"
        # todo: support spec one or other or both in config
        if self.ludicrous_speed and output_return_code != 0:
            return "term"
        # todo learn just client or server (by masking on symbol) in config
        # output_symbol_request = "skip"
        # output_symbol_response = "skip"
        return str(output_return_code) + "-" + output_symbol_response + "-" + output_symbol_request
