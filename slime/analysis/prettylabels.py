import argparse
import collections
import re
import sys
import os
import json
import subprocess
from typing import Dict, List
from .simplestatemachine import StateMachine


def main():
    parser = argparse.ArgumentParser(description="Add a legend and replace arbitrary symbols with names")
    parser.add_argument("-a", action="store", type=str, default="output_alphabet_legend.json",
                        help="name of alphabet file (hint add names to legend keys in output_alphabet_examples.json)")
    parser.add_argument("-p", action="store_true",
                        help="used 'parsed' key as legend")
    parser.add_argument("-e", action="store_true",
                        help="used 'example' key as legend")
    parser.add_argument("-d", action="store", type=str, default="learnedModel_pretty.dot",
                        help="name of dot model file (pretty version)")
    args = parser.parse_args()

    # set legend key
    assert not (args.p and args.e)
    legend_key = "parsed" if args.p else "example" if args.e else "legend"

    # read alphabet file
    with open(args.a, "r") as f:
        alphabet = json.load(f)

    # read dot file
    with open(args.d, "r") as f:
        dot_file = f.readlines()

    # map to/from master alphabet with translations when using consistentlabeler
    # TODO

    # process dot file
    transition_re = r"s\d+ -> s(\d+) "
    colour_re = r"<TR><TD BGCOLOR=\"#[0-9a-f]{6}\">(<font color=\"white\">)?"
    transition_label_re = r"\">(.+) / (\d+|null)-(\d+|null)<"
    state_mapping = collections.defaultdict(set)
    legend = set()
    new_dot = []
    current_transition_dest = None
    for line in dot_file:
        if match := re.search(transition_re, line):
            # track the destination the transitions are leading to
            current_transition_dest = match.group(1)
        elif match := re.search(colour_re, line):
            # add colour + input alphabet symbol to the legend
            legend_entry = match.group(0)
            match = re.search(transition_label_re, line)
            if match is None:
                print(line)
            assert match is not None
            if "font" in legend_entry:
                legend.add(legend_entry + match.group(1).replace("<font color=\"white\">", "") + "</font></TD></TR>\n")
            else:
                legend.add(legend_entry + match.group(1) + "</TD></TR>\n")
            # map the next request to the destination state
            if re.fullmatch(r"\d+", match.group(3)):
                state_mapping[current_transition_dest].add(alphabet[match.group(3)][legend_key])
            # create a new transition label with just the response and colour
            if re.fullmatch(r"\d+", match.group(2)):
                new_label = alphabet[match.group(2)][legend_key]
            else:
                new_label = match.group(2)
            if "font" in legend_entry:
                line = line.replace(match.group(0), "\"><font color=\"white\">%s<" % new_label)
            else:
                line = line.replace(match.group(0), "\">%s<" % new_label)
        elif not line.strip():
            # empty line (setting to none is just so an exception is raised if dot is formatted differently)
            current_transition_dest = None
        # append the line
        new_dot.append(line)

    # update state labels
    for i in range(len(new_dot)):
        if match := re.match(r".+s(\d+).+label=\"(\d+)\".+", new_dot[i]):
            if match.group(1) in state_mapping:
                new_dot[i] = new_dot[i].replace("circle", "oval")
                old_label = "label=\"%s\"" % match.group(2)
                new_label = "label=\"%s\"" % (match.group(2) + "\n" + "\n".join(state_mapping[match.group(1)]))
                new_dot[i] = new_dot[i].replace(old_label, new_label)

    # insert legend
    for i in reversed(range(len(new_dot))):
        if "}" in new_dot[i]:
            new_dot.insert(i, '</TABLE>>]\n')
            for line in legend:
                new_dot.insert(i, line)
            new_dot.insert(i, '<TR><TD>Legend</TD></TR>\n')
            new_dot.insert(i, '<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">\n')
            new_dot.insert(i, 'graph [labelloc="b" labeljust="r" label=<\n')
            break

    # write new file
    new_dot_path = args.d.replace(".dot", "_legend.dot")
    with open(new_dot_path, "w") as f:
        f.writelines(new_dot)
    subprocess.run(["dot", "-Tpng", new_dot_path, "-o", new_dot_path.replace(".dot", ".png")])

if __name__ == "__main__":
    sys.exit(main())
