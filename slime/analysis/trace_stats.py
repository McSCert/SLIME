import argparse
import os
import json
import copy
import re
import subprocess


def read_trace_json(trace_file):
    """Reads a trace file json and returns a dictionary"""
    with open(trace_file, 'r') as f:
        return json.load(f)

def read_all_traces(trace_dir, trace_type="max", ignored_states=[], list_of_states=[]):
    """Reads all the trace files in a directory and all sub directories and returns a dictionary of dictionaries"""
    # folder name is the current state, file name is the transition label and next state
    trace_files = {}
    for root, dirs, files in os.walk(trace_dir):
        for file in files:
            if file.endswith(".json"):
                # get the current state from the folder name
                current_state = os.path.basename(root)
                # get the transition label and next state from the file name
                transition = os.path.splitext(file)[0].split("-state-")[0]
                next_state = os.path.splitext(file)[0].split("-state-")[1].split("-")[0]
                # get whether it's the min max or diff file
                file_type = os.path.splitext(file)[0].split("-state-")[1].split("-")[1]
                # get the trace file
                trace_file = os.path.join(root, file)
                # add the trace file to the dictionary with the current state as the key, and the transition and next state as the value
                if file_type == trace_type and next_state not in ignored_states and (len(list_of_states) == 0 or next_state in list_of_states):
                    if current_state in trace_files:
                        trace_files[current_state][transition + "-state-" + next_state] = read_trace_json(trace_file)
                    else:
                        trace_files[current_state] = {transition + "-state-" + next_state: read_trace_json(trace_file)}
    return trace_files

def combine_traces(trace_files):
    """Combines a dictionary of trace files into a single dictionary"""
    combined_trace = {}
    for current_state, transitions in trace_files.items():
        for transition, trace in transitions.items():
            for key, value in trace.items():
                if key in combined_trace:
                    combined_trace[key] += value
                else:
                    combined_trace[key] = value
    return combined_trace

def get_number_of_values(trace, use_total_calls=False):
    """Returns the number of values for each key in a dictionary"""
    number_of_values = 0
    for key, value in trace.items():
        if use_total_calls:
            number_of_values += len(value)
        else:
            number_of_values += len(set(value))
    return number_of_values

def get_percent_coverage(trace_files, use_percent=False, use_total_calls=False):
    """Returns the percent coverage for each trace in a dictionary of traces"""
    total_number_of_values = get_number_of_values(combine_traces(trace_files), use_total_calls)
    print("total number of distinct functions called:", total_number_of_values)
    if use_percent == False:
        total_number_of_values = 1
    percent_coverage = {}
    for current_state, transitions in trace_files.items():
        for transition, trace in transitions.items():
            if current_state in percent_coverage:
                percent_coverage[current_state][transition] = get_number_of_values(trace, use_total_calls) / total_number_of_values
            else:    
                percent_coverage[current_state] = {}
                percent_coverage[current_state][transition] = get_number_of_values(trace, use_total_calls) / total_number_of_values
    return percent_coverage

def create_dot_file(percent_coverage, use_percent=False):
    """Creates a dot file for a dictionary of trace files"""
    dot_file = "digraph G {\n__start0 [label=\"\" shape=\"none\"];\n\n"
    # add states
    for current_state, transitions in percent_coverage.items():
        dot_file += f"\t{current_state} [shape=\"circle\" label=\"{current_state[1:]}\"];\n"
    # add transitions
    for current_state, transitions in percent_coverage.items():
        for transition, coverage in transitions.items():
            next_state = transition.split("-state-")[1]
            if use_percent:
                coverage = f"{coverage:.2%}"
            else:
                coverage = f"{coverage:.0f}"
            transition = transition.split("-state-")[0].split("-")[2]
            dot_file += f"\t{current_state} -> {next_state} [label=\"{transition} {coverage}\"];\n"
    dot_file += "}"
    # write dot file
    with open("trace_stats.dot", 'w') as f:
        f.write(dot_file)

def create_unique_json(trace_dir, trace_type, uniqueness):
    # read all the trace files
    trace_files = {}
    for state in os.listdir(trace_dir):
        trace_files[state] = {}
        for transition in os.listdir(os.path.join(trace_dir, state)):
            if transition.endswith(trace_type + ".json"):
                trace_files[state][transition] = read_trace_json(os.path.join(trace_dir, state, transition))
    # find the unique function calls for each transition
    unique_trace_files = copy.deepcopy(trace_files)
    for state, transitions in trace_files.items():
        for transition in transitions.keys():
            other_trace_files_without_current = copy.deepcopy(trace_files)
            if uniqueness == "all":
                # compare to all other transitions in all states
                del other_trace_files_without_current[state][transition]
            elif uniqueness == "other-states":
                # compare to all other transitions in all other states, so not any other transition in the same state
                del other_trace_files_without_current[state]
            elif uniqueness == "own-state":
                # compare only to other transitions in the same state
                other_trace_files_without_current = {state: copy.deepcopy(trace_files[state])}
                del other_trace_files_without_current[state][transition]
            other_function_calls = combine_traces(other_trace_files_without_current)
            for key, value in transitions[transition].items():
                if key in other_function_calls:
                    unique_trace_files[state][transition][key] = list(set(value) - set(other_function_calls[key]))
                    if len(unique_trace_files[state][transition][key]) == 0:
                        del unique_trace_files[state][transition][key]
    # write the unique function calls to a json file
    for state, transitions in unique_trace_files.items():
        for transition, trace in transitions.items():
            with open(os.path.join(trace_dir, state, transition.replace(trace_type + ".json", "unique.json")), 'w') as f:
                json.dump(trace, f, indent=2)

def create_state_annotated_dot(trace_dir, trace_type, dot_file_path, function_file_filter, state_mapping_file):
    # read state mapping if provided
    state_mapping = {}
    if state_mapping_file:
        with open(state_mapping_file, 'r') as f:
            state_mapping = json.load(f)
    # if state mapping file was provided, need to flip the states since the key is the old state name (matches trace) and the value is the new state name (matches dot file)
    state_mapping = {f"s{v}": k for k, v in state_mapping.items()}
    # read all the trace files
    trace_files = {}
    for state in os.listdir(trace_dir):
        trace_files[state] = {}
        for transition in os.listdir(os.path.join(trace_dir, state)):
            if transition.endswith(trace_type + ".json"):
                trace_files[state][transition] = read_trace_json(os.path.join(trace_dir, state, transition))
                # filter out functions that are not in the function file, using first file that matches, once found an endswith match in one file, uses the same file for all transitions
                for file in trace_files[state][transition]:
                    if file.endswith(function_file_filter):
                        function_file_filter = file
                        break
                if function_file_filter in trace_files[state][transition]:
                    trace_files[state][transition] = sorted(trace_files[state][transition][function_file_filter])
                else:
                    trace_files[state][transition] = []
    # read the dot file
    with open(dot_file_path, 'r') as f:
        dot_file = f.readlines()
    new_dot_file = []
    # update dot file with state annotations
    start = True
    current_state = ""
    for line in dot_file:
        # copy all lines, only adding new ones when needed
        new_dot_file.append(line)
        # end
        if line.startswith("__start0"):
            continue
        # get state mapping from the dot file (key) to the trace files (value)
        # I forget why the old code used labels, now the names don't change, unless internally renamed with slime.states -i, otherwise only the labels are *renamed*
        # only do this if a state mapping file was not provided
        if not state_mapping_file:
            if line.strip().startswith("s") and line.strip().endswith("];"):
                dot_state = line.strip().split()[0]
                state_label = line.strip().split('label="')[1].split('"')[0]
                # state_mapping[dot_state] = f"s{state_label}" # use the labels to correspond to the trace files
                state_mapping[dot_state] = dot_state # use the dot state names to correspond to the trace files
        # get current state (in terms of state names used in the traces)
        if "->" in line:
            current_state = line.split(" -> ")[0].strip()
            current_state = state_mapping[current_state]
            continue
        # look for transition symbols
        if line.strip().startswith("<TR><TD"):
            transition = re.search(r'">([^>]+?)</', line).group(1)
            transition_symbol = transition.split(" / ")[0]
            # print(f"Looking for function calls for transition {transition_symbol} in state {current_state}")
            # get function calls for this transition
            function_calls = None
            if current_state not in trace_files:
                # print(f"State {current_state} not found in trace files, probably because it is an end state or was ignored with --rm or --rm-term")
                continue
            for trace_file in trace_files[current_state].keys():
                if transition_symbol == trace_file.split("-")[2]:
                    function_calls = trace_files[current_state][trace_file]
                    break
            assert function_calls is not None, f"Could not find trace file for transition {transition_symbol} in state {current_state}"
            # add function calls to dot file
            for function_call in function_calls:
                # print(f"Adding function call {function_call} for transition {transition_symbol} in state {current_state}")
                function_call = function_call.replace("<", "&lt;").replace(">", "&gt;")
                new_dot_file.append(f"\t\t\t<TR><TD></TD><TD>{function_call}</TD></TR>\n")
    # write dot file
    with open(dot_file_path.replace(".dot", "_trace.dot"), 'w') as f:
        f.writelines(new_dot_file)
    subprocess.run(["dot", "-Tpng", dot_file_path.replace(".dot", "_trace.dot"), "-o", dot_file_path.replace(".dot", "_trace.png")])


def main():
    parser = argparse.ArgumentParser(description='Creates a dot file for a trace directory')
    parser.add_argument('trace_dir', type=str, help='The directory of the trace files')
    parser.add_argument('--trace-type', type=str, help='The type of trace file to use (max, min, diff)', default="max")
    parser.add_argument('--rm', help="list of states to ignore", nargs='+', default=[])
    parser.add_argument('--percent', help="use percentages (of total seen distinct functions), instead of total number of distinct functions called", action="store_true")
    parser.add_argument("--unique", type=str, default="", choices=["all", "other-states", "own-state"],
                        help="get unique function calls for each transition, not used anywhere else (this option, and only this one also works on cleaned up dirs renamed with slime.states)", action="store")
    parser.add_argument("--dot", nargs=2, type=str, metavar=("learnedModel_pretty.dot", "function_file_filter"),
                        help="create a dot file from a learnedModel_pretty.dot file and include called functions from function_file_filter found in the trace files", action="store")
    parser.add_argument("--state-map", type=str, default="",
                        help="provide a state_mapping.json file if applying this to an internally renamed pretty state dot (slime.states -i)", action="store")
    args = parser.parse_args()
    if args.unique:
        return create_unique_json(args.trace_dir, args.trace_type, args.unique)
    if args.dot:
        return create_state_annotated_dot(args.trace_dir, args.trace_type, args.dot[0], args.dot[1], args.state_map)
    trace_files = read_all_traces(args.trace_dir, args.trace_type, args.rm)
    percent_coverage = get_percent_coverage(trace_files, args.percent, use_total_calls=False)
    # write json of percent coverage
    with open("trace_stats.json", 'w') as f:
        json.dump(percent_coverage, f, indent=4)
    create_dot_file(percent_coverage, args.percent)
    os.system("dot -Tpng trace_stats.dot -o trace_stats.png")

if __name__ == "__main__":
    main()
