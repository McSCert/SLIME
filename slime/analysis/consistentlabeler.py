import argparse
import re
import sys
import os
import json
import subprocess
from typing import Dict, List
from .simplestatemachine import StateMachine


def main():
    parser = argparse.ArgumentParser(description="Create diagram with consistent state and transition labels by creating a master list of states and alphabet symbols")
    parser.add_argument("-a", action="store", type=str, default="output_alphabet.json",
                        help="name of alphabet file")
    parser.add_argument("-d", action="store", type=str, default="learnedModel_pretty.dot",
                        help="name of dot model file")
    # parser.add_argument("-p", action="store", type=str, default="learnedModel_pretty.dot",
    #                     help="name of pretty dot model file")
    parser.add_argument("-f", action="store", type=str, nargs="+", metavar="folder",
                        help="folder(s) containing models and alphabets")
    args = parser.parse_args()

    # create lists of paths
    assert(len(args.f)) >= 1
    alphabet_paths = [os.path.join(f, args.a) for f in args.f]
    dot_paths = [os.path.join(f, args.d) for f in args.f]
    # pretty_dot_paths = [os.path.join(f, args.p) for f in args.f]

    # read alphabet files
    alphabets: List[Dict] = []
    for a in alphabet_paths:
        with open(a, "r") as f:
            alphabets.append(json.load(f))

    # read dot files
    dot_files: List[List] = []
    for d in dot_paths:
        with open(d, "r") as f:
            dot_files.append(f.readlines())

    # # read pretty dot files
    # pretty_dot_files: List[List] = []
    # for d in pretty_dot_paths:
    #     with open(d, "r") as f:
    #         pretty_dot_files.append(f.readlines())

    # create master alphabet and translations
    master_alphabet = {}
    translation_alphabets = []
    for i in range(len(alphabets)):
        translation_alphabets.append({})
        for key, value in alphabets[i].items():
            if key not in master_alphabet:
                master_alphabet[key] = str(len(master_alphabet) + 1)
            translation_alphabets[i][value] = master_alphabet[key]

    # update transition labels
    for i in range(len(dot_files)):
        # files
        for j in range(len(dot_files[i])):
            # lines in file
            if re.match(r".+ / \d+-\d+.+", dot_files[i][j]):
                # TODO ADD PARAMETER FOR FORMAT LATER, THIS WAS HARD CODED FOR RES-REQ IN PRETTY MODEL
                symbols = re.search(r"(\d+)-(\d+)", dot_files[i][j])
                replacement = "%s-%s" % (translation_alphabets[i][symbols.group(1)], translation_alphabets[i][symbols.group(2)])
                dot_files[i][j] = dot_files[i][j].replace(symbols.group(0), replacement, 1)
            elif re.match(r".+ / \d+-null.+", dot_files[i][j]):
                # TODO ADD PARAMETER FOR FORMAT LATER, THIS WAS HARD CODED FOR RES-REQ IN PRETTY MODEL
                symbols = re.search(r"(\d+)-null", dot_files[i][j])
                replacement = "%s-null" % (translation_alphabets[i][symbols.group(1)])
                dot_files[i][j] = dot_files[i][j].replace(symbols.group(0), replacement, 1)

    # process dot files
    models: List[StateMachine] = []
    for d in dot_files:
        fsm = StateMachine()
        fsm.readDotFile(d)
        models.append(fsm)

    # create state alphabet and translations
    state_alphabet = {}
    state_translations = []
    for i in range(len(models)):
        state_translations.append({})
        for label in sorted(models[i].getStateLabels()):
            models[i].gotoState(label)
            t = models[i].getAvailableTransitions()[:]
            t.sort()
            key = str(t)
            if key not in state_alphabet:
                state_alphabet[key] = str(len(state_alphabet))
            state_translations[i][label] = state_alphabet[key]

    # update state labels
    for i in range(len(dot_files)):
        # files
        for j in range(len(dot_files[i])):
            # lines in file
            match = re.match(r".+(s\d+).+label=\"(\d+)\".+", dot_files[i][j])
            if match:
                line = dot_files[i][j].split("label")
                line[1] = line[1].replace(match.group(2), state_translations[i][match.group(1)])
                dot_files[i][j] = "label".join(line)

    # write new files
    for i in range(len(args.f)):
        base_path = args.f[i]
        master_alphabet_path = os.path.join(base_path, os.path.splitext(args.a)[0] + "_master.json")
        translation_alphabet_path = os.path.join(base_path, os.path.splitext(args.a)[0] + "_translations.json")
        labeled_dot_path = os.path.join(base_path, os.path.splitext(args.d)[0] + "_labeled.dot")
        pngoutput = os.path.join(base_path, os.path.splitext(args.d)[0] + "_labeled.png")
        state_alphabet_path = os.path.join(base_path, "state_alphabet.json")
        state_translation_path = os.path.join(base_path, "state_translations.json")
        with open(master_alphabet_path, "w") as f:
            json.dump(master_alphabet, f)
        with open(translation_alphabet_path, "w") as f:
            json.dump(translation_alphabets[i], f)
        with open(labeled_dot_path, "w") as f:
            f.writelines(dot_files[i])
        with open(state_alphabet_path, "w") as f:
            json.dump(state_alphabet, f)
        with open(state_translation_path, "w") as f:
            json.dump(state_translations[i], f)
        subprocess.run(["dot", "-Tpng", labeled_dot_path, "-o", pngoutput])

if __name__ == "__main__":
    sys.exit(main())
