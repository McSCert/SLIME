import argparse
import collections
import json
import re
import sys
import os
import subprocess
import statistics
from math import floor
from .simplestatemachine import StateMachine

def find_naughty_transitions(fsm: StateMachine, happy_path: list, naughty_transitions: set, max_depth: int, depth: int, current_state: str, last_happy_state: str, happy_count: int) -> bool:
    """return whether to add the previous transition to naughty_transitions"""
    # base case: reach max depth or return to happy_path
    if current_state in happy_path and current_state != last_happy_state:
        happy_difference = happy_path.index(current_state) - happy_path.index(last_happy_state)
        if happy_count < happy_difference and happy_difference >= 1:
            # print(last_happy_state)
            # print(current_state)
            # print(happy_count)
            # print(happy_difference)
            return True
        else:
            return False
    elif depth >= max_depth:
        return False
    # common case: continue on current path or leave happy path
    is_naughty = False
    fsm.gotoState(current_state)
    for transition in fsm.getAvailableTransitions():
        fsm.gotoState(current_state)
        fsm.transition(transition)
        next_state = fsm.getCurrentState()
        new_happy_count = happy_count
        if "allow" in transition and transition.count("</TD></TR>") == 1:
            # should be ONLY allow is in the transition? because otherwise it could also be 'unhappy' actions, and am running this on the pretty version because it's ~3^transitions x faster
            new_happy_count += 1
        if current_state in happy_path:
            if next_state in happy_path:
                # happy -> happy
                find_naughty_transitions(fsm, happy_path, naughty_transitions, max_depth, depth+1, next_state, next_state, 0)
                if new_happy_count == 0 and happy_path.index(next_state) - happy_path.index(current_state) > 0:
                    naughty_transitions.add("%s -> %s" % (current_state, next_state))
            else:
                # happy -> unhappy
                if find_naughty_transitions(fsm, happy_path, naughty_transitions, max_depth, depth+1, next_state, current_state, new_happy_count):
                    naughty_transitions.add("%s -> %s" % (current_state, next_state))
        else:
            if next_state in happy_path:
                # unhappy -> happy
                if find_naughty_transitions(fsm, happy_path, naughty_transitions, max_depth, depth+1, next_state, last_happy_state, new_happy_count):
                    is_naughty = True
                    naughty_transitions.add("%s -> %s" % (current_state, next_state))
            else:
                # unhappy -> unhappy
                if find_naughty_transitions(fsm, happy_path, naughty_transitions, max_depth, depth+1, next_state, last_happy_state, new_happy_count):
                    is_naughty = True
                    naughty_transitions.add("%s -> %s" % (current_state, next_state))
    return is_naughty


def find_naughty_transitions_v2(prettydot: list, naughty_transitions: set) -> None:
    """iterate over every transition to find naughty ones: any block (combined transition label) without an allow, where the response to a request matches an allow elsewhere"""
    # every item in list should be its own line
    original_prettydot = prettydot
    prettydot = []
    for item in original_prettydot:
        prettydot += item.splitlines()
    # magic regexes for my current prettydot structure (technical debt)
    transition_re = r"(s\d+) -> (s\d+) "
    transition_label_re = r"\">(.+) / (.+?)-(.+?)<"
    # get request each state will emit
    state_request = collections.defaultdict(set)
    state_request["s0"] = set(["INITIAL REQUEST"])  # more technical debt, since first request isn't recorded, fill in later
    current_transition_dest = None
    for line in prettydot:
        if match := re.search(transition_re, line):
            # track the destination the transitions are leading to
            current_transition_dest = match.group(2)
        elif match := re.search(transition_label_re, line):
            # get the request that state will emit
            state_request[current_transition_dest].add(match.group(3))
    assert all(len(state_request[key]) == 1 for key in state_request.keys())
    state_request = {key: state_request[key].pop() for key in state_request.keys()}
    # find pairs for "allow" (now a magic word, and non-allow transitions cannot contain the string allow)
    special_pairs = collections.defaultdict(list)
    current_transition_source = None
    for line in prettydot:
        if match := re.search(transition_re, line):
            # track the destination the transitions are coming from
            current_transition_source = match.group(1)
        elif match := re.search(transition_label_re, line):
            # see if it's an allow
            if "allow" in match.group(1):
                # track the special pair as request: [response, ...]
                special_pairs[state_request[current_transition_source]].append(match.group(2))
    # find other transitions that are the special pairs, but transition differently from the "allow" for that state
    source_request = None
    current_pair = None
    is_naughty, has_allow = False, False
    for line in prettydot:
        if match := re.search(transition_re, line):
            # get the current transition pair or record the previous one if it was naughty
            if is_naughty and not has_allow:
                naughty_transitions.add(current_pair)
            current_pair = "%s -> %s" % (match.group(1), match.group(2))
            source_request = state_request[match.group(1)]
            is_naughty, has_allow = False, False
        elif match := re.search(transition_label_re, line):
            # check if it is naughty or has an allow
            if "allow" in match.group(1):
                has_allow = True
            elif match.group(2) in special_pairs[source_request]:
                is_naughty = True
    if is_naughty and not has_allow:
        naughty_transitions.add(current_pair)


class DotCleaner(StateMachine):

    def clean_transition_labels(self):
        # EXAMPLE:
        # s2 -> s0 [label="q0-send_nonces-m0-r1 / send_noncesERROR"];
        # s2 -> s0 [label="q0-send_nonces-m0-r2 / send_noncesERROR"];
        # s2 -> s3 [label="q0-send_nonces-m0-r3 / send_nonces"];
        # BECOMES:
        # s2 -> s0 [label="send_noncesERROR-r1"];
        # s2 -> s0 [label="send_noncesERROR-r2"];
        # s2 -> s3 [label="send_nonces-r3"];
        for i in range(len(self.transitions)):
            for j in range(len(self.transitions[i])):
                # split input symbol and output symbol
                t = self.transitions[i][j].split(" / ")
                # check if mitm action is in symbol and combine
                if len(t[0].split("-")) >= 2 and t[0].split("-")[-1][0] == "r":
                    t[1] = t[1] + "-" + t[0].split("-")[-1]
                self.transitions[i][j] = t[1]

    def replace_transition_labels(self, legend: dict):
        # EXAMPLE:

        # BECOMES:

        for i in range(len(self.transitions)):
            for j in range(len(self.transitions[i])):
                # split input symbol and output symbol
                transition = self.transitions[i][j].split(" / ", 1)  # mitm action / msg
                transition[0] = transition[0].split("-")[1] # m-action-rr
                # todo: split and re-add trace stats
                # clean up msg/output symbol
                new_t = []
                for t in transition[1].split("-"):  # return code-response-next request
                    if t in legend and legend[t]["legend"]:
                        new_t.append(legend[t]["legend"])
                    else:
                        new_t.append(t)
                new_t[0] = transition[1].split("-")[0]  # return/exit code of mitm fuzzer
                if new_t[0] == "0":
                    _  = new_t.pop(0)
                transition[1] = " - ".join(new_t)
                self.transitions[i][j] = " / ".join(transition)

    def add_trace_stats_to_labels(self, trace_stats: dict):
        for i in range(len(self.transitions)):
            for j in range(len(self.transitions[i])):
                # split input symbol and output symbol
                transition = self.transitions[i][j].split(" / ", 1)  # mitm action / msg
                transition[0] = transition[0].split("-")[1] # m-action-rr
                # find corresponding trace stats
                if f"s{i}" in trace_stats:
                    possible_stats = trace_stats[f"s{i}"]
                    for possible_transition in possible_stats:
                        if possible_transition.split("-")[-1] == f"s{j}":
                            possible_input_symbol = "-".join(possible_transition.split("-")[1:4]) # m-action-rr
                            if possible_input_symbol == transition[0]:
                                self.transitions[i][j] = f"{self.transitions[i][j]} ({int(possible_stats[possible_transition])})"

    def add_time_to_labels(self, time_log: list):
        for line in time_log:
            cmds, times = line.strip().split(",")
            cmds = cmds.split(";")
            times = times.split(";")
            if times == [""]:
                continue
            # add time(s) to transition labels
            self.reset()
            for i in range(min(len(cmds), len(times))):
                # found_transition = False
                for j in range(len(self.getAvailableTransitions())):
                    if self.getAvailableTransitions()[j].split(" / ")[0] == cmds[i]:
                        self.getAvailableTransitions()[j] = f"{self.getAvailableTransitions()[j]}TT{times[i]}"
                        self.transition(self.getAvailableTransitions()[j])
                        # found_transition = True
                        break
                # can't check this because terminated commands are not in the transition list
                # if not found_transition:
                #     raise Exception(f"Could not find transition for {cmds[i]} at state {self.current_state_index} in {self.getAvailableTransitions()}")
        # average time(s) for each transition label
        for i in range(len(self.transitions)):
            for j in range(len(self.transitions[i])):
                t = self.transitions[i][j].split("TT")
                t = [float(x) for x in t[1:]]
                if not t:
                    continue
                average_time = sum(t) / len(t)
                average_time = round(average_time, 2)
                self.transitions[i][j] = f"{self.transitions[i][j].split('TT')[0]} ({average_time})"
                # check if any time is more than 50% above or below average (outlier)
                for k in range(1, len(t)):
                    if t[k] > average_time * 1.5 or t[k] < average_time * 0.5:
                        print("Outlier:", t[k], "for", self.transitions[i][j], "at state", i, "to state", self.nexts[i][j])

    def combine_similar_transitions(self):
        # EXAMPLE:
        # s2 -> s0 [label="send_noncesERROR-r1"];
        # s2 -> s0 [label="send_noncesERROR-r2"];
        # s2 -> s3 [label="send_nonces-r3"];
        # BECOMES:
        # s2 -> s0 [label="send_noncesERROR-r1-r2"];
        # s2 -> s3 [label="send_nonces-r3"];
        for i in range(len(self.transitions)):
            t = []
            t_remove = []
            for j in range(len(self.transitions[i])):
                t_j = self.transitions[i][j].split("-")
                # check if similar one exists, if so combine
                if t_j[0] in t and self.nexts[i][j] == self.nexts[i][t.index(t_j[0])]:
                    self.transitions[i][t.index(t_j[0])] += t_j[-1]
                    # still want to keep index good
                    t.append(t_j[0])
                    t_remove.append(j)
                else:
                    t.append(t_j[0])
            # remove extra transitions
            for j in reversed(t_remove):
                temp = self.transitions[i].pop(j)
                temp = self.nexts[i].pop(j)

    def concentrate_edges(self, html = True):
        # combine transition arrows when they have the same start and end, then combine corresponding labels in a box, learnlib seems to have them sorted in a way that I don't need to here
        for i in range(len(self.nexts)):
            j = 0
            while j + 1 < len(self.nexts[i]):
                k = j + 1
                while k < len(self.nexts[i]):
                    if self.nexts[i][j] == self.nexts[i][k]:
                        self.nexts[i].pop(k)
                        if html:
                            self.transitions[i][j] = self.transitions[i][j] + self.transitions[i].pop(k)
                        else:
                            self.transitions[i][j] = self.transitions[i][j] + "\\n" + self.transitions[i].pop(k)
                    else:
                        k += 1
                j += 1

    def html_colour_edges(self, seed = [4379892], step = 3, gen_colours = True):
        t = []
        c = seed
        PHI = (1 + 5**(0.5))/2

        for i in range(len(self.transitions)):
            for j in range(len(self.transitions[i])):
                transition = self.transition_filter(self.transitions[i][j])
                if transition not in t:
                    t.append(transition)
                    if gen_colours:
                        colour = c[-1]
                        for k in range(step):
                            colour = (floor(colour/65536 * PHI)*65536 + floor((colour%65536)/256 * PHI)*256 + floor(colour%256 * PHI)) % 16777216
                        c.append(colour)
                colour = "%06x" % c[t.index(transition)]
                hexr = int(str(colour)[0:2], 16)
                hexg = int(str(colour)[2:4], 16)
                hexb = int(str(colour)[4:6], 16)
                # colour "ADD" Green and "REM" Red
                diff_colour = "<TD></TD>"
                if self.transitions[i][j].startswith("ADD"):
                    diff_colour = "<TD BGCOLOR=\"#00FF00\">ADD</TD>"
                    self.transitions[i][j] = self.transitions[i][j][3:]
                elif self.transitions[i][j].startswith("REM"):
                    diff_colour = "<TD BGCOLOR=\"#FF0000\">REM</TD>"
                    self.transitions[i][j] = self.transitions[i][j][3:]
                # apply colour and background, making sure there is enough contrast
                if (max(hexr,hexg,hexb) - min(hexr,hexg,hexb) < 0x80 and sum([hexr,hexg,hexb]) < 0x180) or sum([hexr,hexg,hexb]) < 0xB0:
                    self.transitions[i][j] = '\t\t\t<TR>' + diff_colour + '<TD BGCOLOR="#' + colour + '"><font color="white">' + self.transitions[i][j] + '</font></TD></TR>\n'
                else:
                    self.transitions[i][j] = '\t\t\t<TR>' + diff_colour + '<TD BGCOLOR="#' + colour + '">' + self.transitions[i][j] + '</TD></TR>\n'

    def transition_filter(self, transition):
        # filter the transition to its 'base form' for grouping together similar colours
        return transition.split(" / ")[0].strip("ADD").strip("REM")


def main():
    parser = argparse.ArgumentParser(description="Create a prettier dot file from the statelearner output (can only parse dot files of this structure) and writes to <inputname>_pretty.dot and <inputname>_pretty.png")
    parser.add_argument(dest="dot", action="store", type=str, metavar="path",
                        help="learnedModel.dot file")
    # parser.add_argument("-c", action="store_true",
    #                     help="generate a distinct colour for each edge label")
    # parser.add_argument("-g", action="store_true",
    #                     help="group edges with the same start and end node")
    parser.add_argument("-a", action="store", type=str,
                        help="name of alphabet file (hint add names to legend keys in output_alphabet_examples.json)")
    parser.add_argument("--trace-stats", action="store", type=str,
                        help="annotate transition labels with values from trace_stats.json")
    parser.add_argument("--acccolour", action="store", type=int,
                        help="use accessible colours, uses n colours for palette, (n = 3-7)")
    parser.add_argument("--nocolour", action="store_true",
                        help="don't colour transitions")
    parser.add_argument("--rm", action="store", type=str, nargs="+", default=[], metavar="state",
                        help="remove state(s) and all connected edges")
    parser.add_argument("--rm-term", action="store_true",
                        help="remove terminal states (states with 'term' transitions leading to them)")
    parser.add_argument("--rm-noflow", action="store_true",
                        help="remove states with no flow transitions leading to them")
    parser.add_argument("--happy", action="store_true",
                        help="colour the happy path")
    parser.add_argument("--dashv1", action="store_true",
                        help="dash arrows for 'naughty' transitions")
    parser.add_argument("--dashv2", action="store_true",
                        help="dash arrows for 'naughty' transitions")
    parser.add_argument("--diff", action="store_true",
                        help="diff'd state machine, look for ADD/REM in the transition labels, and format them differently")
    parser.add_argument("--paper", action="store", type=str, metavar="output_alphabet_examples.json",
                        help="use letters instead of numbers for transition symbols, - -> +, write legend.txt, this is how I lay it out in the paper")
    parser.add_argument("--time", action="store", type=str, metavar="time_log.csv",
                        help="use time_log.csv to annotate transitions with time taken to execute each one")
    args = parser.parse_args()

    assert args.dot.endswith(".dot")
    with open(args.dot, "r") as f:
        fsmdot = f.readlines()

    # find term and noflow states
    if args.rm_term or args.rm_noflow:
        transition_re = re.compile(r"s\d+ -> (s\d+) ")
        for line in fsmdot:
            if transition_re.search(line):
                if (args.rm_term and "term" in line) or (args.rm_noflow and "noflow" in line):
                    dest_state = transition_re.search(line).group(1)
                    args.rm.append(dest_state)
        args.rm = list(set(args.rm))

    # easier to remove states with preprocessing, since simplestatemachine has no remove method, and needs to be refactored before I'd consider adding this to it
    if args.rm:
        clean_dot = []
        state_re = re.compile(r"(s\d+) ")
        transition_re = re.compile(r"s\d+ -> s\d+ ")
        for line in fsmdot:
            if transition_re.search(line):
                state_labels = state_re.findall(line)
                if state_labels[0] not in args.rm and state_labels[1] not in args.rm:
                    clean_dot.append(line)
            elif state_re.search(line):
                state_label = state_re.search(line).group(1)
                if state_label not in args.rm:
                    clean_dot.append(line)
            else:
                clean_dot.append(line)
        fsmdot = clean_dot

    fsm = DotCleaner()
    fsm.readDotFile(fsmdot)

    # fsm.clean_transition_labels()
    # fsm.combine_similar_transitions()
    if args.time:
        with open(args.time, "r") as f:
            time_log = f.readlines()
        fsm.add_time_to_labels(time_log)
    if args.trace_stats:
        with open(args.trace_stats, "r") as f:
            trace_stats = json.load(f)
        fsm.add_trace_stats_to_labels(trace_stats)
    if args.a:
        with open(args.a, "r") as f:
            alphabet = json.load(f)
        fsm.replace_transition_labels(alphabet)
    #if args.c:
    if args.acccolour:
        if args.acccolour == 3:
            colours = [0xe5f5e0, 0xa1d99b, 0x31a354]
        elif args.acccolour == 4:
            colours = [0xedf8e9, 0xbae4b3, 0x74c476, 0x238b45]
        elif args.acccolour == 5:
            colours = [0xedf8e9, 0xbae4b3, 0x74c476, 0x31a354, 0x006d2c]
        elif args.acccolour == 6:
            colours = [0xedf8e9, 0xc7e9c0, 0xa1d99b, 0x74c476, 0x31a354, 0x006d2c]
        elif args.acccolour == 7:
            colours = [0xedf8e9, 0xc7e9c0, 0xa1d99b, 0x74c476, 0x41ab5d, 0x238b45, 0x005a32]
        else:
            raise ValueError("Invalid number of colours")
        fsm.html_colour_edges(seed = colours, step = 0, gen_colours=False)
        happy_path_highlight = '[style="bold" color="blue" '
    elif args.nocolour:
        fsm.html_colour_edges(seed = [16777215], step = 0)
        happy_path_highlight = '[style="bold" '
    else:
        fsm.html_colour_edges()
        happy_path_highlight = '[color="blue" '
    #if args.g:
    fsm.concentrate_edges()

    prettydot = fsm.generateDot()

    # cleanup alphabet symbol format (will probably change in code too for next run and won't need this)
    for i in range(len(prettydot)):
        prettydot[i] = prettydot[i].replace("-rr / 0-", " / ")
        prettydot[i] = prettydot[i].replace("-rr / ", " / ")
        prettydot[i] = prettydot[i].replace("m-", "")

    if args.happy:
        # find states along happy path
        happy_path = ["s0"]
        happy_labels = []
        state_re = re.compile(r"(s\d+) ")
        transition_re = re.compile(r"s\d+ -> s\d+ ")
        transition_label_re = re.compile(r"label=\"(.+)\"")
        for passes in range(10):
            for line in fsmdot:
                if transition_re.search(line):
                    state_labels = state_re.findall(line)
                    if "allow" in line and state_labels[0] == happy_path[-1]:
                        happy_path.append(state_labels[1])
                        transition_label = transition_label_re.search(line).group(1)
                        happy_labels.append(transition_label)
                        if happy_path.count(state_labels[0]) >= 2:
                            break
        # add coloured lines to prettydot
        for i in range(0, len(happy_path) - 1):
            for j in range(len(prettydot)):
                happy_transition = "%s -> %s" % (happy_path[i], happy_path[i+1])
                if happy_transition in prettydot[j]:
                    prettydot[j] = prettydot[j].replace("[", happy_path_highlight)
                    break
        # find transitions that indicate SUT misbehaviour
        if args.dashv1 or args.dashv2:
            naughty_transitions = set()
            if args.dashv1:
                find_naughty_transitions(fsm, happy_path, naughty_transitions, 15, 0, "s0", "s0", 0)
            if args.dashv2:
                find_naughty_transitions_v2(prettydot, naughty_transitions)
            # print(happy_path)
            # print(naughty_transitions)
            for transition in naughty_transitions:
                for i in range(len(prettydot)):
                    if transition in prettydot[i] and happy_path_highlight not in prettydot[i]:  # don't dash blue lines, messy and conveys no useful info, obvious when non-allow transitions can replace an allow since lines are combined
                        prettydot[i] = prettydot[i].replace("[", '[style="dashed" ')
                        break

    if args.diff:
        for i in range(len(prettydot)):
            if " -> " in prettydot[i]:
                if "REM" in prettydot[i]:
                    prettydot[i] = prettydot[i].replace("REM", "-")
                    prettydot[i] = prettydot[i].replace("[", '[style="dashed"')
                    # prettydot[i] = prettydot[i].replace('<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">\n', '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">\n\t\t\t<TR><TD BGCOLOR="#C0392B">REMOVED</TD></TR>\n')
                if "ADD" in prettydot[i]:
                    prettydot[i] = prettydot[i].replace("ADD", "+")
                    prettydot[i] = prettydot[i].replace("[", '[style="dashed"')
                    # prettydot[i] = prettydot[i].replace('<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">\n', '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">\n\t\t\t<TR><TD BGCOLOR="#27AE60">ADDED</TD></TR>\n')

    if args.paper:
        # read legend, the structure is "new_symbol" = legend["old_symbol"]["legend"], if "legend" is empty, use "parsed" instead
        with open(args.paper, "r") as f:
            legend = json.load(f)
        for i in range(len(prettydot)):
            if " -> " in prettydot[i]:
                # get symbols, only interested in the integers, can be multiple symbols pairs per "transition" since in pretty structure
                symbols = re.findall(r" (\d+|null)-(\d+|null)(<| )", prettydot[i])
                for symbol in symbols:
                    # replace symbol with letters here
                    if symbol[0] == "null":
                        symbol0 = chr(len(legend)+1 + 64)
                    else:
                        symbol0 = chr(int(symbol[0]) + 64)
                    if symbol[1] == "null":
                        symbol1 = chr(len(legend)+1 + 64)
                    else:
                        symbol1 = chr(int(symbol[1]) + 64)
                    # replace symbols in prettydot
                    prettydot[i] = prettydot[i].replace(" %s-%s%s" % (symbol[0], symbol[1], symbol[2]), " %s + %s%s" % (symbol0, symbol1, symbol[2]))
        # crete legend
        legend_txt = ""
        for symbol in legend:
            legend_txt += "%s -> %s\n" % (chr(int(symbol) + 64), legend[symbol]["legend"] if legend[symbol]["legend"] else legend[symbol]["parsed"])
        legend_txt += "%s -> %s" % (chr(len(legend)+1 + 64), "null")

    head, tail = os.path.split(args.dot)
    fsmoutput = os.path.join(head, os.path.splitext(tail)[0] + "_pretty.dot")
    pngoutput = os.path.join(head, os.path.splitext(tail)[0] + "_pretty.png")

    with open(fsmoutput, "w") as f:
        f.writelines(map(lambda l: l + '\n', prettydot))

    subprocess.run(["dot", "-Tpng", fsmoutput, "-o", pngoutput])

    if args.paper:
        with open(os.path.join(head, os.path.splitext(tail)[0] + "_pretty_legend.txt"), "w") as f:
            f.write(legend_txt)

if __name__ == "__main__":
    sys.exit(main())
