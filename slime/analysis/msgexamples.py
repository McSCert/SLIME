import collections
import argparse
import re
import sys
import os
import json
import pickle


def main():
    args = argparse.ArgumentParser(description="Get all messages from fuzzer.pickle and create all_output_alphabet_examples.json")
    args.add_argument("--log", type=str, default="fuzzer.pickle", help="fuzzer.pickle file")
    args.add_argument("--alphabet", type=str, default="output_alphabet_examples.json", help="alphabet file")
    args.add_argument("--output", type=str, default="all_output_alphabet_examples.json", help="output file")
    args = args.parse_args()

    # read the pickle file
    msg_log = []
    with open(args.log, 'rb') as f:
        while True:
            try:
                msg_log.append(pickle.load(f))
            except EOFError:
                break

    # read the alphabet file
    with open(args.alphabet, 'r') as f:
        alphabet = json.load(f)

    for symbol in alphabet.keys():
        del alphabet[symbol]["example"]
        alphabet[symbol]["log"] = []

    # get all the messages
    for msgs in msg_log:
        for msg in msgs:
            alphabet[msg["symbol"]]["log"].append(msg["message"])
            alphabet[msg["symbol"]]["log"].append("- "*30)

    # write the alphabet file
    with open(args.output, 'w') as f:
        json.dump(alphabet, f, indent=2)

if __name__ == "__main__":
    sys.exit(main())
