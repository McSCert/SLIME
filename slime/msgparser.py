# Standard library
import collections
import re
import os
import json
import pickle
import sys
import typing
# Local
from .utils import readJson, writeCsv, writeJson
# Third Part
import xmltodict

class MessageParserData:
    def __init__(self) -> None:
        self.output_alphabet_symbols = {}
        self.output_alphabet_examples = {}
        self.parser_errors = []

    def readSymbols(self):
        assert os.path.isfile("logs/output_alphabet.json")
        prev_symbols = readJson("logs/output_alphabet.json")
        prev_examples = readJson("logs/output_alphabet_examples.json")
        assert prev_symbols  # very import that this was read and not empty, otherwise resuming is meaningless
        # make sure they are consistent (having 2 files has some redundancy, but don't feel like changing it now)
        for k, v in prev_symbols.items():
            assert v in prev_examples, "output_alphabet.json and output_alphabet_examples.json are not consistent"
            assert prev_examples[v]["parsed"] == k, "output_alphabet.json and output_alphabet_examples.json are not consistent"
        for k, v in prev_examples.items():
            assert v["parsed"] in prev_symbols, "output_alphabet.json and output_alphabet_examples.json are not consistent"
            assert prev_symbols[v["parsed"]] == k, "output_alphabet.json and output_alphabet_examples.json are not consistent"
        # copy over so references between objects are kept
        for key in prev_symbols:
            self.output_alphabet_symbols[key] = prev_symbols[key]
        for key in prev_examples:
            self.output_alphabet_examples[key] = prev_examples[key]

    def writeSymbols(self):
        writeJson("logs/output_alphabet.json", self.output_alphabet_symbols)
        writeJson("logs/output_alphabet_examples.json", self.output_alphabet_examples)

    def writeParserErrors(self):
        writeCsv("logs/parser_errors.csv", self.parser_errors, False)

class MessageParser:
    """base class"""
    def __init__(self, data: MessageParserData):
        self.data = data
        self.output_alphabet_symbols = data.output_alphabet_symbols
        self.output_alphabet_examples = data.output_alphabet_examples
        self.parser_errors = data.parser_errors

    def lookupSymbol(self, key: str, original_message: str = "", message_source: str = "UNKNOWN") -> str:
        if str(key) not in self.output_alphabet_symbols:
            self.output_alphabet_symbols[str(key)] = str(len(self.output_alphabet_symbols) + 1)
            self.output_alphabet_examples[str(len(self.output_alphabet_symbols))] = {"example": str(original_message), "parsed": str(key), "source": message_source, "request": False, "response": False, "legend": ""}
            self.data.writeSymbols()
        return self.output_alphabet_symbols[str(key)]

    def logError(self, error):
        self.parser_errors.append(error)
        self.data.writeParserErrors()

    def recursiveDictKeys(self, d:typing.Union[dict, list]) -> list:
        if type(d) in [dict, collections.OrderedDict]:
            keys = list(d.keys())
            for k in d.keys():
                if type(d[k]) in [dict, collections.OrderedDict, list]:
                    keys += self.recursiveDictKeys(d[k])
        elif type(d) == list:
            keys = []
            for i in d:
                if type(i) in [dict, collections.OrderedDict, list]:
                    keys += self.recursiveDictKeys(i)
        return sorted(keys)

    def parse(self, message: str, message_type: str, message_source: str = "UNKNOWN") -> str:
        try:
            if message in ["MITM_TIMEOUT", ""]:
                parsed_message = message
            else:
                parsed_message = self.parser(message, message_type)
            output_symbol = self.lookupSymbol(parsed_message, message, message_source)
            self.output_alphabet_examples[output_symbol][message_type] = True
            return output_symbol
        except:
            self.logError(message_type + ":" + message)
            return "PARSE_ERROR"

    def parser(self, message: str, message_type: str) -> str:
        raise NotImplementedError

class json_parser(MessageParser):
    def parser(self, response, message_type: str):
        # use json.dumps(result, sort_keys=True) to serialize
        json_response = json.loads(str(response))
        if type(json_response) == dict or type(json_response) == list:
            response = self.recursiveDictKeys(json_response)
        else:
            raise Exception("PARSE_ERROR")
        # create a separtate parser for hex key replacement later
        for i in range(len(response)):
            if re.match("^[0-9a-f]+$", response[i]):
                response[i] = "HEX_KEY"
        return response

class xml_parser(MessageParser):
    def parser(self, response, message_type: str):
        xml_response = xmltodict.parse(response)
        response_parsed = self.recursiveDictKeys(xml_response)
        return response_parsed

class xml_string_parser(MessageParser):
    def parser(self, response, message_type: str):
        # find all text between <string> </string> tags
        response_parsed = re.findall(r"<string>(.*?)</string>", response)
        response_parsed = " ".join(response_parsed)        
        return response_parsed

class string_parser(MessageParser):
    def parser(self, response, message_type: str):
        return str(response)

class string_len_parser(MessageParser):
    def parser(self, response, message_type: str):
        return str(len(str(response))) + str(message_type)

class deprecated_parsers(MessageParser):
    def request_parser(self, response):
        response = str(response)
        response = response.split(":443")[1][:-1]
        return response

    def response_parser(self, response):
        if type(response) == bytes:
            response = pickle.loads(response)
        else:
            response = pickle.loads(eval(response))
        headers = response[0]
        headers = re.sub(r"b'", "'", headers)
        headers = re.sub(r"Headers\[", "{", headers)
        headers = re.sub(r"\]", "}", headers)
        # headers = re.sub(r", (?='[^']+?'\))", ": ", headers) should be equivalent to below
        headers = re.sub(r", (?=[^\(])", ": ", headers)
        headers = re.sub(r"\(", "", headers)
        headers = re.sub(r"\)", "", headers)
        headers = re.sub(r"'", "\"", headers)
        headers = json.loads(headers)
        if response[1] != "":
            content = json.loads(response[1])
            headers.update(content)
        response = self.recursiveDictKeys(headers)
        return response

    def vars_parser(self, response:list):
        # may need to import libraries for respective objects
        if type(response) == bytes:
            response = pickle.loads(response)
        else:
            response = pickle.loads(eval(response))
        d = {}
        # k = []
        for ob in response:
            if type(ob) == str:
                if ob != "":
                    d.update(json.loads(ob))
                    # k += self.recursiveDictKeys(json.loads(ob))
            elif type(ob) == dict:
                d.update(ob)
                # k += self.recursiveDictKeys(ob)
            elif hasattr(ob, "__dict__"):
                ob_dict = vars(ob)
                if "fields" in ob_dict.keys():
                    # this part is probably specific to mitmproxy Http Header
                    if type(ob_dict["fields"]) == tuple:
                        ob_dict = dict(ob_dict["fields"])
                d.update(ob_dict)
                # k += self.recursiveDictKeys(vars(ob))
            else:
                raise Exception("OBJECT ERROR")
        response = self.recursiveDictKeys(d)
        # response = sorted(k)
        return response

def select_msgparser(data: MessageParserData, parser: str = "json_parser", user_module = None) -> MessageParser:
    if user_module and hasattr(user_module, parser):
        return getattr(user_module, parser)(data)
    else:
        return getattr(sys.modules[__name__], parser)(data)
