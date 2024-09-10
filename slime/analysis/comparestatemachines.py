import argparse
import os
import json
import sys
from .simplestatemachine import StateMachine

def readDotFile(fsm_path, transition_label_re = r"label=\"(.+?) /.+\""):
    if os.path.splitext(fsm_path)[1] == ".dot":
        with open(fsm_path, "r") as f:
            fsmdot = f.readlines()
        fsm = StateMachine()
        fsm.readDotFile(fsmdot, transition_label_re=transition_label_re)
        return fsm
    else:
        sys.exit()

def getUniqueLabel(existing_labels, base_label):
    new_label = base_label
    i = 0
    while new_label in existing_labels:
        new_label = "%s_C%s" %(base_label, i)
        i += 1
    return new_label

def constructCombinedStateMachine(equivalent_state_mappings):
    state_machine = StateMachine()
    state_machine.addState("s0")
    for A_state in equivalent_state_mappings.keys():
        for B_state in equivalent_state_mappings[A_state].keys():
            for transition_sequence in equivalent_state_mappings[A_state][B_state]:
                distance_from_target = len(transition_sequence)
                for transition in transition_sequence:
                    distance_from_target -= 1
                    if state_machine.transition(transition) == False:
                        if distance_from_target == 0:
                            new_state = "A%s_B%s" %(A_state, B_state)
                        else:
                            new_state = "A%s_B%s_D%s" %(A_state, B_state, distance_from_target)
                        state_machine.addState(new_state)
                        state_machine.addTransition(state_machine.getCurrentState(), new_state, transition)
                        state_machine.transition(transition)
                    elif distance_from_target == 0:
                        # overwriting another 'target' state shouldn't be possible unless the equivalent state mapping is wrong, but this state could already exist with a lower C# from a different transition sequence with keep_all
                        current_label = state_machine.getCurrentState()
                        new_label = "A%s_B%s" %(A_state, B_state)
                        if "D" in current_label:
                            state_machine.renameState(current_label, new_label)
                        elif new_label not in current_label:
                            state_machine.renameState(current_label, current_label + "___" + new_label)
                state_machine.reset()
    return state_machine

def compareStateMachinesRecursionOptimised(fsm_a, fsm_b, equivalent_state_mappings, available_transitions, depth_remaining):
    for t in available_transitions(fsm_a, fsm_b):
        fsm_a_copy = fsm_a.shallowCopy()
        fsm_b_copy = fsm_b.shallowCopy()
        fsm_a_copy.transition(t)
        fsm_b_copy.transition(t)
        equivalent_state_mappings[fsm_a_copy.getCurrentState()].add(fsm_b_copy.getCurrentState())
        if depth_remaining > 0:
            compareStateMachinesRecursionOptimised(fsm_a_copy, fsm_b_copy, equivalent_state_mappings, available_transitions, depth_remaining-1)

def compareStateMachinesRecursion(fsm_a, fsm_b, equivalent_state_mappings, available_transitions, depth_remaining, transitions_sequence, keep_all):
    for t in available_transitions(fsm_a, fsm_b):
        fsm_a_copy = fsm_a.shallowCopy()
        fsm_b_copy = fsm_b.shallowCopy()
        fsm_a_copy.transition(t)
        fsm_b_copy.transition(t)
        new_transition_sequence = transitions_sequence + [t]
        if fsm_b_copy.getCurrentState() in equivalent_state_mappings[fsm_a_copy.getCurrentState()]:
            if keep_all:
                equivalent_state_mappings[fsm_a_copy.getCurrentState()][fsm_b_copy.getCurrentState()].append(new_transition_sequence)
            elif len(new_transition_sequence) < len(equivalent_state_mappings[fsm_a_copy.getCurrentState()][fsm_b_copy.getCurrentState()][0]):
                equivalent_state_mappings[fsm_a_copy.getCurrentState()][fsm_b_copy.getCurrentState()] = [new_transition_sequence]
        else:
            equivalent_state_mappings[fsm_a_copy.getCurrentState()][fsm_b_copy.getCurrentState()] = [new_transition_sequence]
        if depth_remaining > 0:
            compareStateMachinesRecursion(fsm_a_copy, fsm_b_copy, equivalent_state_mappings, available_transitions, depth_remaining-1, new_transition_sequence, keep_all)

def CompareStateMachines(fsm_a, fsm_b, max_depth, save_transitions, save_all, override_transitions, re_a, re_b):
    # init
    fsm_a = readDotFile(fsm_a, re_a)
    fsm_b = readDotFile(fsm_b, re_b)
    equivalent_state_mappings = {}
    if override_transitions == False:
        available_transitions = lambda fsm_a, fsm_b : set(fsm_a.getAvailableTransitions()).intersection(fsm_b.getAvailableTransitions())
    else:
        available_transitions = lambda fsm_a, fsm_b : override_transitions
    # choose version of algorithm to run
    if not save_transitions:
        for label in fsm_a.getStateLabels():
            equivalent_state_mappings[label] = set()
        compareStateMachinesRecursionOptimised(fsm_a, fsm_b, equivalent_state_mappings, available_transitions, max_depth)
        for label in fsm_a.getStateLabels():
            equivalent_state_mappings[label] = list(equivalent_state_mappings[label])
    else:
        for label in fsm_a.getStateLabels():
            equivalent_state_mappings[label] = {}
        compareStateMachinesRecursion(fsm_a, fsm_b, equivalent_state_mappings, available_transitions, max_depth, [], save_all)
    # save mapping
    if save_all == False: # do you want a 500MB json file, cause that's how you get a 500MB json file
        with open("compared.json", "w") as f:
            json.dump(equivalent_state_mappings, f, indent=4, separators=(',', ': '))
    # save combined state machine
    if save_transitions:
        fsm = constructCombinedStateMachine(equivalent_state_mappings)
        with open("compared.dot", "w") as f:
            f.writelines(map(lambda l: l + '\n', fsm.generateDot(html=False, renumber_states=False)))

def main():
    parser = argparse.ArgumentParser(description="Find mapping of states from A to B via transitions")
    parser.add_argument("fsm_a", action="store", type=str,
                        help="Path of FSM A dot file")
    parser.add_argument("fsm_b", action="store", type=str,
                        help="Path of FSM B dot file")
    parser.add_argument("--rea", action="store", type=str, default=r"label=\"(.+?) /.+\"",
                        help="Regex for common key of FSM A transition label")
    parser.add_argument("--reb", action="store", type=str, default=r"label=\"(.+?) /.+\"",
                        help="Regex for common key of FSM B transition label")
    parser.add_argument("-d", action="store", type=int, default=5,
                        help="Max recursion depth")
    parser.add_argument("-s", action="store_true",
                        help="Save one possible transition sequence for each mapping")
    parser.add_argument("-k", action="store_true",
                        help="Save all tested transition sequences for each mapping")
    parser.add_argument("-o", action="store", nargs="+", default=False, metavar="transition_label",
                        help="Override transitions and assume every state has these and only these available")
    args = parser.parse_args()
    CompareStateMachines(args.fsm_a, args.fsm_b, args.d, args.s, args.k, args.o, args.rea, args.reb)


if __name__ == "__main__":
    sys.exit(main())
