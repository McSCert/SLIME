# Standard library
import csv
import json
import os
import typing
import collections
import pickle
import time
import inspect
import types
from functools import wraps
# Third party
from loguru import logger
import psutil


def decorate_all_in_module(module, decorator):
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, types.FunctionType):
            setattr(module, name, decorator(obj))
        elif isinstance(obj, type):
            setattr(module, name, for_all_methods(decorator)(obj))


def for_all_methods(decorator):
    def decorate(cls):
        for attr in cls.__dict__:
            if callable(getattr(cls, attr)):
                setattr(cls, attr, decorator(getattr(cls, attr)))
        return cls
    return decorate

def loguru_decorator(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        caller_frame = inspect.currentframe().f_back
        extra = {
            "full_func": f"{fn.__module__}:{fn.__name__}:{fn.__code__.co_firstlineno}",
            "caller_func": f"{caller_frame.f_globals['__name__']}:{caller_frame.f_code.co_name}:{caller_frame.f_lineno}"
        }
        extra["func_entry_exit"] = f"{extra['caller_func']} -> {extra['full_func']}"
        logger.bind(**extra).info(f"Entering with args={args} and kwargs={kwargs}")
        result = fn(*args, **kwargs)
        extra["func_entry_exit"] = f"{extra['caller_func']} <- {extra['full_func']}"
        logger.bind(**extra).info(f"Exiting with result={result}")
        return result
    return wrapper

def readJson(fName:str) -> dict:
    if os.path.exists(fName):
        with open(fName, "r", encoding="utf-8", errors="surrogateescape") as json_file:
            data = json.load(json_file, object_pairs_hook=collections.OrderedDict)
        return data
    return {}

def writeJson(fName:str, data:dict, indent:int = 1, skipkeys:bool = False) -> None:
    if not os.path.isdir(os.path.dirname(fName)):
        os.makedirs(os.path.dirname(fName))
    with open(fName, "w", encoding="utf-8", errors="surrogateescape") as json_file:
        json.dump(data, json_file, indent=indent, separators=(',', ': '), skipkeys=skipkeys)

def writeCsv(fName:str, data:list, is_2d_array:bool = True) -> None:
    if not os.path.isdir(os.path.dirname(fName)):
        os.makedirs(os.path.dirname(fName))
    with open(fName, "w", newline="", encoding="utf-8", errors="backslashreplace") as f:
        writer = csv.writer(f, delimiter=",")
        if is_2d_array:
            for row in data:
                writer.writerow(row)
        else:
            for row in data:
                writer.writerow([row])

# def restart():
#     os.execl(sys.executable, sys.executable, *sys.argv)

def terminator(ports:list, useos:bool = True):
    if useos:
        for port in ports:
            os.system("sudo fuser -k " + str(port) + "/tcp")
    else:
        conns = psutil.net_connections()
        for con in conns:
            if con.laddr.port in ports:
                try:
                    p = psutil.Process(con.pid)
                    p.terminate()
                    print(con)
                except:
                    print("ERROR: " + str(con))

class LearnlibCommandLog:
    def __init__(self, resume = False, time = False, ludicrous_speed = False, plaid = False):
        if resume:
            assert not os.path.exists("logs/log.pickle.bak")
            os.rename("logs/log.pickle", "logs/log.pickle.bak")
            self.old_log_file = open("logs/log.pickle.bak", "rb")
        self.pickle_file = open("logs/log.pickle", "wb")
        self.csv_file = open("logs/log.csv", "w", newline='')
        self.log_writer = csv.writer(self.csv_file)
        self.time_file = open("logs/time_log.csv", "w", newline='')
        self.time_writer = csv.writer(self.time_file)
        self.log_entry = {"timestamp":{}}
        self.lookup_dict = {}
        self.ludicrous_lookup = {}
        self.plaid_lookup = {}
        self.plaid_equivalencies = collections.defaultdict(set)
        self.time = time
        self.ludicrous_speed = ludicrous_speed
        self.plaid = plaid

    def resume_next(self) -> tuple:
        try:
            self.log_entry = pickle.load(self.old_log_file)
            return self.log_entry["query"], self.log_entry["response"]
        except Exception:
            self.old_log_file.close()
            return None, None

    def lookup_query(self, query, plaid_recursion = False) -> str:
        query_split = query.split(";")
        if query in self.lookup_dict:
            return self.lookup_dict[query]
        if self.ludicrous_speed:
            for i in range(1, len(query_split)):
                short_query = ";".join(query_split[:-i])
                if short_query in self.ludicrous_lookup:
                    response, end = self.ludicrous_lookup[short_query]
                    print("light speed, too slow?")
                    return response + (";" + end) * i
        if self.plaid and not plaid_recursion:
            for i in range(1, len(query_split)):
                short_query = ";".join(query_split[:-i])
                if short_query in self.plaid_lookup:
                    plaid_msg = self.plaid_lookup[short_query]
                    for short_equivalent_query in self.plaid_equivalencies[plaid_msg]:
                        if short_query == short_equivalent_query:
                            continue
                        equivalent_query = short_equivalent_query + ";" + ";".join(query_split[-i:])
                        if len(equivalent_query.split(";")) != len(query_split):
                            continue
                        response = self.lookup_query(equivalent_query, plaid_recursion=True)
                        if response is not None:
                            print("they've gone to plaid!")
                            return response
        return None

    def cache_query(self):
        query, response = self.log_entry["query"], self.log_entry["response"]
        query_split, response_split = query.split(";"), response.split(";")
        self.lookup_dict[query] = response
        for i in range(1, len(query_split) - 1):
            self.lookup_dict[";".join(query_split[:-i])] = ";".join(response_split[:-i])
        if self.ludicrous_speed:
            if "term" in response:
                # This is a little safer, may use a separate flag from the next two, or just use always
                i = response_split.index("term") + 1
                self.ludicrous_lookup[";".join(query_split[:i])] = (";".join(response_split[:i]), "term")
            # elif "errorres" in response:
            #     # Handle same as term
            #     i = response_split.index("errorres") + 1
            #     self.ludicrous_lookup[";".join(query_split[:i])] = (";".join(response_split[:i]), "errorres")
            # elif "errorreq" in response:
            #     # Handle same as term
            #     i = response_split.index("errorreq") + 1
            #     self.ludicrous_lookup[";".join(query_split[:i])] = (";".join(response_split[:i]), "errorreq")
            elif "noflow" in response:
                # warning, this might not always be true (for all systems tested so far it is true), assumes communication does not resume/restart after a noflow
                i = response_split.index("noflow") + 1
                self.ludicrous_lookup[";".join(query_split[:i])] = (";".join(response_split[:i]), "noflow")
            elif response_split[-1].split("-")[-1] == "null":
                # TODO Create flag for null request terminates as noflow
                # warning, this might not always be true (for all systems tested so far it is true), assumes communication does not resume/restart after a noflow
                self.ludicrous_lookup[query] = (response, "noflow")
        if self.plaid and "plaid_msg" in self.log_entry and self.log_entry["plaid_msg"]:
            self.plaid_lookup[self.log_entry["query"]] = self.log_entry["plaid_msg"]
            self.plaid_equivalencies[self.log_entry["plaid_msg"]].add(self.log_entry["query"])

    def new_entry(self):
        """create an empty dict for the new entry"""
        self.log_entry = {"timestamp":{}}
    
    def update_entry(self, label, content):
        self.log_entry[label] = content
        self.log_entry["timestamp"][label] = str(time.time())

    def close(self):
        self.pickle_file.close()
        self.csv_file.close()

    def write_entry(self, used_query):
        # todo: this will just dump (append) current entries to file
        if "query" in self.log_entry and "response" in self.log_entry:
            # write entry
            self.log_entry["used_query"] = used_query
            if self.time:
                row = [self.log_entry["query"], self.log_entry["timestamp"]["query"], self.log_entry["response"], self.log_entry["timestamp"]["response"]]
            else:
                row = [self.log_entry["query"], self.log_entry["response"]]
            self.log_writer.writerow(row)
            self.csv_file.flush()
            row = [self.log_entry["query"], self.log_entry["transition_times"]]
            self.time_writer.writerow(row)
            self.time_file.flush()
            pickle.dump(self.log_entry, self.pickle_file)
            self.pickle_file.flush()
            self.cache_query()
            self.new_entry()
        else:
            print("LOG ERROR: " + str(self.log_entry.keys()))
