import argparse
import pickle
import sys
import os
import code
import json
import subprocess
import time
import traceback
import re
from .simplestatemachine import StateMachine

# def start_container():
#     cmd_start = ["sudo", "podman", "run", "--name", "covgenhtml", "-it", "aktualizr_client2"]
#     subprocess.run(cmd_start)

# annotate trace
# def get_html_cov(lcov):
#     # todo: integrate with sutctrl and slime main
#     cmd_cov_push = ["sudo", "podman", "cp", "fsmhtml/" + lcov, "covgenhtml:/home/aktualizr/build/"]
#     cmd_cov_pull = ["sudo", "podman", "cp", "covgenhtml:/home/aktualizr/build/html", os.path.join(os.getcwd(), "fsmhtml", os.path.splitext(lcov)[0])]
#     cmd_cov_html = ["sudo", "podman", "exec", "covgenhtml", "genhtml", "-q", "-o", "/home/aktualizr/build/html", os.path.join("/home/aktualizr/build/", lcov)]
#     subprocess.run(cmd_cov_push)
#     subprocess.run(cmd_cov_html)
#     time.sleep(0.5)
#     subprocess.run(cmd_cov_pull)

def cov_diff(cov_a, cov_b):
    diff = {}
    for source_file in cov_a:
        if source_file in cov_b:
            diff_file = sorted(set(cov_a[source_file]) - set(cov_b[source_file]))
            if diff_file:
                diff[source_file] = diff_file
        else:
            diff[source_file] = sorted(cov_a[source_file])
    return diff

def cov_intersection(cov_a, cov_b):
    intersection = {}
    for source_file in cov_a:
        if source_file in cov_b:
            intersection[source_file] = sorted(set(cov_a[source_file]) & set(cov_b[source_file]))
    return intersection

def cov_union(cov_a, cov_b):
    union = {}
    for source_file in cov_a:
        if source_file in cov_b:
            union[source_file] = sorted(set(cov_a[source_file]) | set(cov_b[source_file]))
        else:
            union[source_file] = sorted(set(cov_a[source_file]))
    for source_file in cov_b:
        if source_file not in union:
            union[source_file] = sorted(set(cov_b[source_file]))
    return union

def filter_callgrind_output(trace: str, keep_regex: str = "^/home/aktualizr"):
    # https://www.valgrind.org/docs/manual/cl-format.html
    # https://stackoverflow.com/questions/7761448/filter-calls-to-libc-from-valgrinds-callgrind-output
    # https://sourceforge.net/p/valgrind/mailman/valgrind-users/thread/e847e3a9-0d10-4c5e-929f-51258ecf9dfc@iris/
    trace = pickle.loads(eval(trace))
    file_dict = {}
    fn_dict = {}
    ob_dict = {}
    filtered_trace = []
    json_trace = {}  # just which functions and files of interest have been hit
    last_file = ""
    keep_file = True
    keep_ob = True
    keep_cob = True
    keep_cob_sub_found_calls = True
    keep_cob_sub_found_not0 = True
    for line in trace.splitlines():
        if re.match("c?(ob|fi|fl|fe|fn)=.+", line):
            # decompress strings
            match = re.search("^c?(ob|fi|fl|fe|fn)=\((\d+)\) ?(.+)?", line)
            if match.group(3):
                if "ob" in match.group(1):
                    if match.group(2) in ob_dict and ob_dict[match.group(2)] != match.group(3):
                        raise Exception("Error: inconsistent ob file name")
                    ob_dict[match.group(2)] = match.group(3)
                elif "fn" in match.group(1):
                    # json trace (extra)
                    if match.group(2) in fn_dict and fn_dict[match.group(2)] != match.group(3):
                        raise Exception("Error: inconsistent function name")
                    fn_dict[match.group(2)] = match.group(3)
                else:
                    # filter files (extra)
                    if match.group(2) in file_dict and file_dict[match.group(2)] != match.group(3):
                        raise Exception("Error: inconsistent file name")
                    file_dict[match.group(2)] = match.group(3)
            # decide whether to keep next section or not
            if line.startswith("ob"):
                if re.search(keep_regex, ob_dict[match.group(2)]):
                    keep_ob = True
                    keep_file = True
                    filtered_trace.append(line)
                else:
                    keep_ob = False
            elif line.startswith("cob"):
                if re.search(keep_regex, ob_dict[match.group(2)]):
                    keep_cob = True
                    keep_file = True
                    filtered_trace.append(line)
                else:
                    keep_cob = False
                    keep_cob_sub_found_calls = False
                    keep_cob_sub_found_not0 = False
            elif "fn" in match.group(1):
                # json trace (extra)
                if keep_file:
                    if not fn_dict[match.group(2)].startswith("0x") and fn_dict[match.group(2)] not in json_trace[last_file]:
                        json_trace[last_file].append(fn_dict[match.group(2)])
            else:
                # filter files (extra)
                if re.search(keep_regex, file_dict[match.group(2)]):
                    keep_file = True
                    filtered_trace.append(line)
                    # json trace
                    last_file = file_dict[match.group(2)]
                    if last_file not in json_trace:
                        json_trace[last_file] = []
                else:
                    keep_file = False
        else:
            # keep or discard line
            if keep_ob:
                if keep_cob:
                    if keep_file:
                        filtered_trace.append(line)
                else:
                    # skip until finding the first non-0 starting line afters calls=
                    if keep_cob_sub_found_calls:
                        if keep_cob_sub_found_not0:
                            if keep_file:
                                filtered_trace.append(line)
                        elif not line.startswith("0"):
                            if keep_file:
                                filtered_trace.append(line)
                            keep_cob_sub_found_not0 = True
                    elif line.startswith("calls="):
                        keep_cob_sub_found_calls = True
    return "\n".join(filtered_trace), json_trace


def filter_uflow_output(trace: str, keep_str: str = "tuf"):
    filtered_trace = []
    json_trace = {}  # just which functions and files of interest have been hit
    for line in trace.splitlines():
        if " -> " in line:  # keep_str in line and 
            filtered_trace.append(line)
            start = line.index(" -> ") + 4
            line = line[start:].split(".")
            file_name = ".".join(line[:-1])
            func_name = line[-1]
            if file_name in json_trace:
                json_trace[file_name].append(func_name)
            else:
                json_trace[file_name] = [func_name]
    return "\n".join(filtered_trace), json_trace



def main():
    parser = argparse.ArgumentParser(description="Parse learnedModel.dot and log.pickle to generate code traces for each state transition")
    parser.add_argument(dest="dot", action="store", type=str, metavar="path_dot",
                        help="learnedModel.dot file")
    parser.add_argument(dest="log", action="store", type=str, metavar="path_log",
                        help="log.pickle file")
    parser.add_argument(dest="sut", action="store", type=str, metavar="name",
                        help="name of sut")
    parser.add_argument("-o", "--output", action="store", type=str, metavar="path_out", default=None,
                        help="output directory, default is os.path.commonpath(path_dot, path_log)/trace/")
    parser.add_argument("-i", action="store_true",
                        help="enter interactive shell when done")
    args = parser.parse_args()

    if args.output:
        output_path = args.output
    else:
        output_path = os.path.join(os.path.commonpath([args.dot, args.log]), "trace")

    fsmdot = args.dot
    # droppedFile = droppedFile.replace(os.path.sep, '/')
    # if os.path.splitext(droppedFile)[1] == ".dot":
    #     fsmdot = droppedFile
    # else:
    #     sys.exit()
    # # fsmdot = "../../output/learnedModel.dot"
    slimepickle = args.log
    # droppedFile = droppedFile.replace(os.path.sep, '/')
    # if os.path.splitext(droppedFile)[1] == ".pickle":
    #     slimepickle = droppedFile
    # else:
    #     sys.exit()
    # # slimepickle = "../logs/log.pickle"

    print("Stage 1: Load model and log")
    slimelog = []
    with open(slimepickle, "rb") as f:
        try:
            while True:
                slimelog.append(pickle.load(f))
        except EOFError:
            pass

    with open(fsmdot, "r") as f:
        fsmdot = f.readlines()

    fsm = StateMachine()
    fsm.readDotFile(fsmdot)

    print("Stage 2: Add coverage to fsm")
    l = 1
    last_cov = ""
    filter_output_function = filter_uflow_output
    # get length of preseed (i.e. number of commands before first state transition) if used
    entry = slimelog[0]
    assert "query" in entry and "response" in entry and "traces" in entry, "unexpected first entry in log.pickle"
    preseed_len = len(entry["traces"]) - len(entry["query"].split(";")) - 1
    if preseed_len > 0:
        print("log generated with a preseed length of:", preseed_len)
    try:
        # os.makedirs("trace/init", exist_ok=True)
        for entry_num, entry in enumerate(slimelog):
            if "query" not in entry or "response" not in entry or "traces" not in entry:
                continue
            cmds = entry["query"].split(";")
            res = entry["response"].split(";")
            traces = entry["traces"][preseed_len:]
            # find if flow was terminated early (since those are missing traces) (could also just use trace len, but this validates the log a bit)
            for i in range(len(res)):
                if res[i] in ["term", "noflow"] or res[i].split("-")[-1] == "null":
                    cmds = cmds[:i+1]
                    res = res[:i+1]
                    break
            assert len(cmds) == len(res) == len(traces) - 1, f"unexpected lengths of query: {len(cmds)}, response: {len(res)}, traces: {len(traces)} for entry {entry_num}"
            # trace_str, trace_dict = filter_output_function(traces[0][args.sut])
            # with open("trace/init/session-" + str(l) + ".out", "w") as f:
            #     f.write(trace_str)
            # with open("trace/init/session-" + str(l) + ".json", "w") as f:
            #     json.dump(trace_dict, f, indent=2, separators=(',', ': '), ensure_ascii=False)
            for i in range(len(cmds)):
                ##### group by state (entering)
                # fsm.reset()
                # for j in range(i):
                #     prev_state = fsm.getCurrentState()
                #     fsm.transition(cmds[j] + " / " + res[j])
                # # way to much data to write, writes full trace for every session
                # if i >= 1:
                #     file_name = "prev-" + prev_state + "-cmd-" + cmds[i-1] + "-res-" + res[i-1] + "-session-" + str(l) + ".out"
                # else:
                #     file_name = "session-" + str(l) + ".out"
                # file_name = file_name.replace("q0-null-m0-r", "")
                # file_path = os.path.join("trace", "state_enter", fsm.getCurrentState(), file_name)
                # os.makedirs(os.path.dirname(file_path), exist_ok=True)
                # with open(file_path, "w") as f:
                #     f.write(trace_str)
                # with open(file_path.replace(".out", ".json"), "w") as f:
                #     json.dump(trace_dict, f, indent=2, separators=(',', ': '), ensure_ascii=False)
                ##### group by transitions
                # file_name = "res-" + "-".join(res[0:i+1]) + "-session-" + str(l) + ".out"
                # file_path = os.path.join("trace", "init", *cmds[0:i+1], file_name)
                trace_str, trace_dict = filter_output_function(traces[i+1][args.sut]) # offset of 1 is for the first get_traces() call (first client request leading up to state 0 before the first mitm action), unrelated to preseed, relevant trace is grabbed after each action
                # # way to much data to write, writes full trace for every session
                # os.makedirs(os.path.dirname(file_path), exist_ok=True)
                # with open(file_path, "w") as f:
                #     f.write(trace_str)
                # with open(file_path.replace(".out", ".json"), "w") as f:
                #     json.dump(trace_dict, f, indent=2, separators=(',', ': '), ensure_ascii=False)
                ##### group by state (exiting)
                fsm.reset()
                for j in range(i):
                    fsm.transition(cmds[j] + " / " + res[j])
                fsm.addCoverage(trace_dict, cmds[i] + " / " + res[i])
                # # way to much data to write, writes full trace for every session
                # file_name = "cmd-" + cmds[i] + "-res-" + res[i] + "-session-" + str(l) + ".out"
                # file_name = file_name.replace("q0-null-m0-r", "")
                # file_path = os.path.join("trace", "state_exit", fsm.getCurrentState(), file_name)
                # os.makedirs(os.path.dirname(file_path), exist_ok=True)
                # with open(file_path, "w") as f:
                #     f.write(trace_str)
                # with open(file_path.replace(".out", ".json"), "w") as f:
                #     json.dump(trace_dict, f, indent=2, separators=(',', ': '), ensure_ascii=False)
            
            # cov = Coverage(cov_str, "lcov")
            # # cov.write("cov/" + str(l) + ".info")
            # t = []
            # for i in range(len(cmds)):
            #     t.append(cmds[i] + " / " + res[i])
            # if fsm.addCoverage(t, cov):
            #     pass
            #     # print("Pass " + str(t))
            # else:
            #     print("ERROR LINE: " + str(l))
            l += 1
        print("processed %s lines" % (l-1))
    except:
        print(traceback.format_exc())
        print("EXCEPTION LINE: " + str(l))

    print("Stage 3: Get min and max coverage for each state")
    for i in range(len(fsm.labels)):
        state_label = fsm.labels[i]
        state_cov = fsm.coverage_data[i]
        for transition in state_cov.keys():
            max_cov = state_cov[transition][0]
            min_cov = state_cov[transition][0]
            for cov in state_cov[transition][1:]:
                max_cov = cov_union(max_cov, cov)
                min_cov = cov_intersection(min_cov, cov)
            diff_cov = cov_diff(max_cov, min_cov)
            fsm.current_state_index = i
            fsm.transition(transition)
            file_name = "cmd-" + transition.split("/")[0] + "-res-" + transition.split("/")[1] + "-state-" + fsm.getCurrentState()
            file_name = file_name.replace("q0-null-m0-r", "")
            file_name = file_name.replace(" ", "")
            file_path = os.path.join(output_path, "state_summary", state_label, file_name + "-max.json")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                json.dump(max_cov, f, indent=2, separators=(',', ': '), ensure_ascii=False, sort_keys=True)
            file_path = os.path.join(output_path, "state_summary", state_label, file_name + "-min.json")
            with open(file_path, "w") as f:
                json.dump(min_cov, f, indent=2, separators=(',', ': '), ensure_ascii=False, sort_keys=True)
            file_path = os.path.join(output_path, "state_summary", state_label, file_name + "-diff.json")
            with open(file_path, "w") as f:
                json.dump(diff_cov, f, indent=2, separators=(',', ': '), ensure_ascii=False, sort_keys=True)
            # merge the max coverage with whatever is already in merge (so we can relearn to grab more trace samples)
            file_path = os.path.join(output_path, "state_summary", state_label, file_name + "-merge.json")
            merge_cov = {}
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    merge_cov = json.load(f)
            merge_cov = cov_union(merge_cov, max_cov)
            with open(file_path, "w") as f:
                json.dump(merge_cov, f, indent=2, separators=(',', ': '), ensure_ascii=False, sort_keys=True)

            # fsm.coverage_data[i] = [min_cov, max_cov]
            # fsm.coverage_data[i][0].write("fsmhtml/" + fsm.labels[i] + "_min.info")
            # fsm.coverage_data[i][1].write("fsmhtml/" + fsm.labels[i] + "_max.info")
            # get_html_cov(fsm.labels[i] + "_min.info")
            # get_html_cov(fsm.labels[i] + "_max.info")

    if args.i:
        code.interact(local=locals())
