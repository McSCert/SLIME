import argparse
import csv
import sys
import os
import code
from .simplestatemachine import StateMachine

class LogChecker(StateMachine):
    def constructfsm(self, transitions, currentLine):
        self.reset()
        errorFlag = False
        if self.labels == []:
            self.addState("s0")
            self.state_lines.append([])
        for t in transitions:
            self.state_lines[self.current_state_index].append(currentLine)
            if self.transition(t):
                pass
            else:
                # check for contradiction
                for existingT in self.transitions[self.current_state_index]:
                    # same cmd, different res
                    t_split = t.split(" / ")
                    existingT_split = existingT.split(" / ")
                    if t_split[0] == existingT_split[0] and t_split[1] != existingT_split[1]:
                        print("ERROR STATE: " + self.labels[self.current_state_index] + " Transition: " + t + " Expecting: " + existingT)
                        errorFlag = True
                self.addState("s" + str(len(self.labels)))
                self.state_lines.append([])
                self.addTransition(self.labels[self.current_state_index], self.labels[-1], t)
                self.transition(t)
        self.reset()
        return errorFlag

def main():
    parser = argparse.ArgumentParser(description="Check log for non-determinism or verify against state machine")
    parser.add_argument(dest="log", action="store", type=str, metavar="path",
                        help="log.csv file")
    parser.add_argument("-d", action="store", type=str, metavar="path",
                        help="learnedModel.dot file")
    parser.add_argument("-i", action="store_true",
                        help="enter interactive shell when done")
    args = parser.parse_args()

    if args.log:
        print("Read log")
        mlcsv = os.path.normpath(args.log)
        with open(mlcsv, "r", newline='') as f:
            reader = csv.reader(f)
            mllog = list(reader)

    if args.d:
        print("Load model")
        with open(args.d, "r") as f:
            fsmdot = f.readlines()
        fsm = LogChecker()
        fsm.readDotFile(fsmdot)

    if args.d and args.log:
        # check log for contradictions with dot
        print("Verify model with log")
        l = 1
        try:
            for line in mllog:
                cmds = list(line)[0].split(";")
                res = list(line)[1].split(";")
                t = []
                for i in range(len(cmds)):
                    t.append(cmds[i] + " / " + res[i])
                if fsm.isValid(t):
                    pass
                    # print("Pass " + str(t))
                else:
                    print("ERROR LINE: " + str(l))
                l += 1
        except:
            print("EXCEPTION LINE: " + str(l))

    if args.log:
        # create non minimal state machine from log
        print("Check log for non-determinism")
        testfsm = LogChecker()
        l = 1
        try:
            for line in mllog:
                cmds = list(line)[0].split(";")
                res = list(line)[1].split(";")
                t = []
                for i in range(len(res)):
                    t.append(cmds[i] + " / " + res[i])
                if testfsm.constructfsm(t, l):
                    print("ERROR LINE: " + str(l))
                l += 1
        except:
            print("EXCEPTION LINE: " + str(l))
        # testfsm.pretty()

    print("Check complete!")
    if args.i:
        code.interact(local=locals())


if __name__ == "__main__":
    main()
