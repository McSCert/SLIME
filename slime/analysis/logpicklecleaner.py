import argparse
import code
import csv
import os
import pickle

def write_csv(data: list[dict], columns: list, fname: str):
    with open(fname, "w", newline='') as f:
        writer = csv.writer(f)
        for entry in data:
            row = []
            for c in columns:
                if c in entry:
                    row.append(str(entry[c]))
                    # old style plaid_msg, remove this block later
                    if c == "plaid_msg":
                        if row[-1].startswith("request"):
                            row[-1] = "old_format"
                    # old style plaid_msg, remove this block later
                elif c == "keys":
                    row.append(str(entry.keys()))
                else:
                    row.append("")
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Clean up cruft from logs that occurs on resuming with different parameters and writes to log.pickle.clean")
    parser.add_argument(dest="log", action="store", type=str, metavar="path",
                        help="log.pickle file")
    parser.add_argument("-i", action="store_true",
                        help="enter interactive shell when done")
    parser.add_argument("-n", action="store_true",
                        help="don't write log.pickle.clean when done")
    parser.add_argument("--csv", action="store", type=str, nargs="+", default=None, metavar="column_name",
                        help="write clean_log.csv with specified columns")
    parser.add_argument("--ogcsv", action="store", type=str, nargs="+", default=None, metavar="column_name",
                        help="write original_log.csv with specified columns")
    args = parser.parse_args()

    # file to write to, make sure not to overwrite anything
    assert not os.path.exists("log.pickle.clean")

    print("Read log")
    log_pickle = []
    with open(args.log, "rb") as f:
        try:
            while True:
                log_pickle.append(pickle.load(f))
        except EOFError:
            pass
    
    print("Cleaning log")
    # doesn't entirely get rid of unused entries, but rather deduplicates them
    log_clean = []
    used_queries = []
    for entry in log_pickle:
        if entry["used_query"]:
            log_clean.append(entry)
            used_queries.append(entry["query"])
    for entry in log_pickle:
        if not entry["used_query"]:
            if entry["query"] in used_queries:
                # see if this unused entry contains any useful data still, like trace or plaid
                i = used_queries.index(entry["query"])
                for key in entry.keys():
                    if key not in log_clean[i] or not log_clean[i][key]:
                        log_clean[i][key] = entry[key]
                if "merged" not in log_clean[i]["timestamp"]:
                    log_clean[i]["timestamp"]["merged"] = []
                log_clean[i]["timestamp"]["merged"].append(entry["timestamp"])
            else:
                # keep them if they haven't been used yet
                log_clean.append(entry)

    if not args.n:
        print("Writing log.pickle.clean")
        with open("log.pickle.clean", "wb") as f:
            for entry in log_clean:
                pickle.dump(entry, f)

    if args.csv:
        print("Writing clean_log.csv")
        write_csv(log_clean, args.csv, "clean_log.csv")

    if args.ogcsv:
        print("Writing original_log.csv")
        write_csv(log_pickle, args.ogcsv, "original_log.csv")

    print("Cleaning complete!")
    if args.i:
        code.interact(local=locals())


if __name__ == "__main__":
    main()
