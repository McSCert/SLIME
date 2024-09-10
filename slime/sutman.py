import typing

from .utils import loguru_decorator
from .msgbroker import Bugs
from .msgparser import MessageParser, MessageParserData, select_msgparser

class SutManager:
    @loguru_decorator
    def __init__(self, sut_config:dict, user_module = None):
        self.sut_queues = {}
        self.parser_data = MessageParserData() # TODO: should be shared with mitm too maybe? so symbols are shared with stdout (but also stdout is another type so shouldn't matter)
        self.sut_parsers = {}
        self.sut_by_order = []
        self.sut_to_trace = []
        for sut_name in sut_config:
            # init queue
            self.sut_queues[sut_name] = Bugs(
                sut_name,
                True,
                remote_credentials=sut_config[sut_name]["remote_credentials"]
            )
            self.sut_queues[sut_name].initQueues()
            # init parser
            self.sut_parsers[sut_name] = select_msgparser(self.parser_data, sut_config[sut_name]["msg_parser"], user_module)
            # whether tracing is enabled, outside of controller_options because it lets slime know whether the controller_class supports tracing
            if "enable_tracing" in sut_config[sut_name] and sut_config[sut_name]["enable_tracing"]:
                self.sut_to_trace.append(sut_name)
            # order sut appears in config.json, this is also the startup order
            self.sut_by_order.append(sut_name)

    @loguru_decorator
    def len(self) -> int:
        return len(self.sut_by_order)

    @loguru_decorator
    def names(self) -> list:
        return self.sut_by_order

    @loguru_decorator
    def q(self, sut:typing.Union[int, str]) -> Bugs:
        if type(sut) == int:
            sut = self.sut_by_order[sut]
        return self.sut_queues[sut]

    @loguru_decorator
    def p(self, sut:typing.Union[int, str]) -> MessageParser:
        if type(sut) == int:
            sut = self.sut_by_order[sut]
        return self.sut_parsers[sut]

    @loguru_decorator
    def get_traces(self) -> dict:
        traces = {}
        for sut_name in self.sut_to_trace:
            self.q(sut_name).send("GETTRACE")
            trace = self.q(sut_name).listen()
            traces[sut_name] = trace
        return traces
