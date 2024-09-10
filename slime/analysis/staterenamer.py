import collections
import argparse
import re
import sys
import os
import json
import shutil
import subprocess
from typing import Dict, List
from .simplestatemachine import StateMachine


def apply_state_mapping(state_mapping_path: str, dir_state_summary: str):
    # read state mapping
    with open(state_mapping_path, "r") as f:
        state_mapping = json.load(f)

    # make state_mapping have a default value of "DEL"
    state_mapping = collections.defaultdict(lambda: "DEL", state_mapping)

    assert os.path.isdir(dir_state_summary), "dir_state_summary must be a directory"

    shutil.copytree(dir_state_summary, dir_state_summary + "_states")

    # rename all subfolder from s\d+ to temp\d+ using the state mapping
    for f in os.listdir(dir_state_summary + "_states"):
        os.rename(os.path.join(dir_state_summary + "_states", f), os.path.join(dir_state_summary + "_states", f"temp{state_mapping[f]}"))
        # remove folders that were mapped to "DEL"
        if state_mapping[f] == "DEL":
            shutil.rmtree(os.path.join(dir_state_summary + "_states", f"temp{state_mapping[f]}"))

    # rename all subfolder from temp\d+ to s\d+
    for f in os.listdir(dir_state_summary + "_states"):
        os.rename(os.path.join(dir_state_summary + "_states", f), os.path.join(dir_state_summary + "_states", "s" + f[4:]))

    # rename all files in subfolders from state-s\d+ to state-s\d+ using the state mapping
    for f in os.listdir(dir_state_summary + "_states"):
        for g in os.listdir(os.path.join(dir_state_summary + "_states", f)):
            old_state = re.search(r"state-(s\d+)", g).group(1)
            old_name = os.path.join(dir_state_summary + "_states", f, g)
            new_name = old_name.replace(f"state-{old_state}", f"state-s{state_mapping[old_state]}")
            os.rename(old_name, new_name)
            # remove files that were mapped to "DEL"
            if state_mapping[old_state] == "DEL":
                os.remove(new_name)
                continue
            # give a better name to the file (comment out if broken, quick change for current examples)
            action = new_name.split("-")[2]
            dest = new_name.split("-")[-2]
            summary = new_name.split("-")[-1].split(".")[0]
            newer_name = "-".join([action, dest, summary]) + ".json"
            os.rename(new_name, os.path.join(dir_state_summary + "_states", f, newer_name))


def rename_states_dot(dot_file_path: str, rename_internal: bool, bias: str):
    # read dot file
    with open(dot_file_path, "r") as f:
        dot_file = f.read()

    # find my custom lines which start with "{" then remove and save them to add back
    special_order_lines = []
    for i, line in enumerate(dot_file.split("\n")):
        if line.startswith("{"):
            special_order_lines.append(line)
            dot_file = dot_file.replace(line, "~~~~~")

    # get list of states
    states = re.findall(r"\s(s\d+) ", dot_file)
    states = list(set(states))
    states.sort()

    # get list of transitions, which are structured in the following way:
    # s2 -> s4 [label=
    # <<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">
    # 	<TR><TD></TD><TD BGCOLOR="#e5f5e0">allow / G + C</TD></TR>
    # 	<TR><TD></TD><TD BGCOLOR="#a1d99b">replacereq / G + C</TD></TR>
    #   <TR><TD></TD><TD BGCOLOR="#31a354"><font color="white">smartreplayreq / term</font></TD></TR>
    # </TABLE>>];
    transitions_re_groups = re.findall(r"(s\d+) -> (s\d+) (.+?);", dot_file, re.DOTALL)
    # extract transition labels
    transitions = []
    for s1, s2, t in transitions_re_groups:
        labels = re.findall(r"\">(\w.+?)</", t)
        if bias == "0":
            # remove all "+" and "-" entries from list labels
            labels = [l for l in labels if l != "+" and l != "-"]
        elif bias == "+":
            # find "-" entries, then prepend "~~~" to the next entry so it sorts last
            for i, l in enumerate(labels):
                if l == "-":
                    labels[i + 1] = "~" + labels[i + 1]
            # remove all "+" and "-" entries from list labels
            labels = [l for l in labels if l != "+" and l != "-"]
        elif bias == "-":
            # find "+" entries, then prepend "~~~" to the next entry so it sorts last
            for i, l in enumerate(labels):
                if l == "+":
                    labels[i + 1] = "~" + labels[i + 1]
            # remove all "+" and "-" entries from list labels
            labels = [l for l in labels if l != "+" and l != "-"]
        labels = "".join(list(sorted(labels)))
        transitions.append((s1, s2, t, labels))

    # get happy path (follow only transitions which contain "allow"), first state is always s0 for slime
    happy_path = []
    current_state = "s0"
    while current_state not in happy_path:
        happy_path.append(current_state)
        try:
            current_state = [s2 for s1, s2, t, l in transitions if s1 == current_state and "allow" in t][0]
        except:
            # no more transitions (no loop back in happy path)
            break

    # list of states in new order
    new_state_order = happy_path[:]

    # go through states that are not in the happy path, in order of branch off, than label order
    transition_fork_stack = []  # stack of states that are currently being branched off, so that we don't need recursion
    current_state = "s0"
    happy_path_index = 0
    while len(new_state_order) < len(states):
        # get all next states
        next_states = [(s2, l) for s1, s2, t, l in transitions if s1 == current_state and s2 not in new_state_order]
        # sort by label
        next_states.sort(key=lambda x: x[1])
        # print(next_states)
        # if there are multiple next states, we need to branch off
        if len(next_states) > 1:
            # get next state
            current_state = next_states[0][0]
            # add other possible states to stack
            transition_fork_stack.extend([s for s, l in next_states[1:]])
        elif len(next_states) == 1:
            # only one next state, go there
            current_state = next_states[0][0]
        else:
            # no more branches, go back up the stack if there are any
            if len(transition_fork_stack) > 0:
                current_state = transition_fork_stack.pop()
            else:
                happy_path_index += 1
                current_state = happy_path[happy_path_index]
        # add state to new order
        if current_state not in new_state_order:
            new_state_order.append(current_state)

    # rename states in dot_file
    # states are labeled as such
    # s0 [shape="circle" label="0"];
	# s1 [shape="circle" label="1"];
    for i, s in enumerate(new_state_order):
        dot_file = re.sub(rf'{s} \[shape="circle" label="\d+"\];', rf'{s} [shape="circle" label="{i}"];', dot_file)

    # update internal state names too (make it easier to edit by hand easier and force state placement)
    # ie like in https://stackoverflow.com/questions/34228322/order-boxes-left-to-right-in-dot-graphviz
    # with {rank = same; s4 -> s15 -> s13 -> s11 -> s9 -> s8 [color=invis]}
    if rename_internal:
        dot_file = re.sub(r's(\d+) ', r'TEMP\1 ', dot_file)
        for i, s in enumerate(new_state_order):
            dot_file = re.sub(rf'TEMP{s[1:]} ', rf's{i} ', dot_file)

    # put special lines back in
    for line in special_order_lines:
        dot_file = dot_file.replace("~~~~~", line, 1)

    # write state mapping
    state_mapping = {s: i for i, s in enumerate(new_state_order)}
    with open(dot_file_path.replace(".dot", "_state_mapping.json"), "w") as f:
        json.dump(state_mapping, f, indent=2)

    # write dot_file
    with open(dot_file_path.replace(".dot", "_states.dot"), "w") as f:
        f.write(dot_file)
    subprocess.run(["dot", "-Tpng", dot_file_path.replace(".dot", "_states.dot"), "-o", dot_file_path.replace(".dot", "_states.png")])


def main():
    # this only works because these scripts never change the internal state names in the dot file (s\d+), but only the labels in the state lines s1 [shape="circle" label="1"];
    parser = argparse.ArgumentParser(description="Rename states in learnedModel_pretty.dot in a structured way using the happy path")
    parser.add_argument("-d", action="store", type=str, default="learnedModel_pretty.dot",
                        help="name of dot model file")
    parser.add_argument("-i", action="store_true",
                        help="rename internal state names too (affects visual layout) (will need to provide state_mapping.json to apply to slime.trace)")
    parser.add_argument("-s", action="store", type=str, default="0", choices=["0", "+", "-"],
                        help="bias sorting to prefer (+) new and common states over removed, or (-) old and common states over added, or (0) no bias")
    parser.add_argument("--trace", nargs=2, action="store", type=str, metavar=("state_mapping.json", "dir_state_summary"),
                        help="take a state mapping generated by running this first on learnedModel_pretty.dot and apply it to the state_summary output folder of slime.trace")
    args = parser.parse_args()

    if args.trace:
        assert not args.d
        assert not args.i
        assert not args.s
        apply_state_mapping(args.trace[0], args.trace[1])
    else:
        rename_states_dot(args.d, args.i, args.s)


if __name__ == "__main__":
    sys.exit(main())
