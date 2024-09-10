import re

class StateMachine:
    # needs refactoring
    """
    labels = ["state_label 1", "state_label 2", ...]
    transitions = [["Transition 1 to x", "Transition 1 to y", ... ], ["Transition 2 to x", ...], ...]
    nexts = [["x", "y", ...], ["x", ...], ...]
    """
    def __init__(self):
        self.labels = []
        self.transitions = []
        self.nexts = []
        self.current_state_index = 0
        self.state_lines = []
        self.coverage_data = None
        self.coverage_links = None

    def shallowCopy(self):
        fsm = StateMachine()
        fsm.labels = self.labels
        fsm.transitions = self.transitions
        fsm.nexts = self.nexts
        fsm.current_state_index = self.current_state_index
        return fsm

    def reset(self, initial = 0):
        self.current_state_index = initial

    def addState(self, label):
        if label in self.labels:
            return False
        self.labels.append(str(label))
        self.transitions.append([])
        self.nexts.append([])
        return True

    def renameState(self, old_label, new_label):
        if new_label in self.labels or old_label not in self.labels:
            return False
        elif old_label == new_label:
            return True
        self.labels[self.labels.index(old_label)] = new_label
        for i in range(len(self.nexts)):
            for j in range(len(self.nexts[i])):
                if self.nexts[i][j] == old_label:
                    self.nexts[i][j] = new_label
        return True

    def addTransition(self, current_state_label, next_state_label, transition_label, force = False):
        if force and current_state_label not in self.labels:
            self.addState(current_state_label)
        if current_state_label in self.labels:
            cs = self.labels.index(current_state_label)
            self.transitions[cs].append(transition_label)
            self.nexts[cs].append(next_state_label)
        else:
            raise Exception("Error adding transition from non-existing state (try force next time): %s %s %s" %(current_state_label, next_state_label, transition_label))

    def transition(self, transition_label):
        if transition_label in self.transitions[self.current_state_index]:
            q = self.transitions[self.current_state_index].index(transition_label)
            nextstate = self.nexts[self.current_state_index][q]
            self.current_state_index = self.labels.index(nextstate)
            return True
        else:
            return False

    def gotoState(self, state_label):
        self.current_state_index = self.labels.index(state_label)

    def addCoverage(self, cov, transition = "", transitions = []):
        if self.coverage_data is None:
            self.coverage_data = [{} for i in range(len(self.labels))]
            self.coverage_links = [{} for i in range(len(self.labels))]
        if transitions:
            self.reset()
            for t in transitions[:-1]:
                if self.transition(t):
                    pass
                else:
                    print("ERROR STATE: " + self.labels[self.current_state_index] + " Transition: " + t)
                    return False
            transition = transitions[-1]
        if transition not in self.coverage_data[self.current_state_index]:
            self.coverage_data[self.current_state_index][transition] = [cov]
        else:
            self.coverage_data[self.current_state_index][transition].append(cov)
        return True

    def getCurrentState(self):
        return self.labels[self.current_state_index]

    def getStateLabels(self):
        return self.labels

    def getAvailableTransitions(self):
        return self.transitions[self.current_state_index]

    def getDict(self):
        # probably a better structure to work with internally
        d = {}
        for i in range(len(self.labels)):
            d[self.labels[i]] = {}
            for j in range(len(self.transitions[i])):
                d[self.labels[i]][self.transitions[i][j]] = self.nexts[i][j]
        return d

    def print(self):
        print(self.labels)
        print(self.transitions)
        print(self.nexts)

    def pretty(self, interesting = 0):
        for s in range(len(self.labels)):
            if len(self.transitions[s]) >= interesting:
                print("State: " + self.labels[s])
                for t in range(len(self.transitions[s])):
                    print("%s -> %s [%s]" %(self.labels[s], self.nexts[s][t], self.transitions[s][t]))

    def isValid(self, transitions):
        self.reset()
        for t in transitions:
            if self.transition(t):
                pass
            else:
                print("ERROR STATE: " + self.labels[self.current_state_index] + " Transition: " + t)
                return False
        self.reset()
        return True

    def readGraphviz(self, file_contents):
        # todo, use https://github.com/pygraphviz/pygraphviz
        # alternatives https://github.com/xflr6/graphviz#see-also
        pass

    def generateGraphviz(self):
        pass

    def readDotFile(self, file_contents: list[str],
                    state_re = r"(s\d+) ",
                    transition_re = r"s\d+ -> s\d+ ",
                    transition_label_re = r"label=\"(.+)\""):
        state_re = re.compile(state_re)
        transition_re = re.compile(transition_re)
        transition_label_re = re.compile(transition_label_re)
        for i in range(len(file_contents)):
            line = file_contents[i]
            if transition_re.search(line):
                j = i
                state_labels = state_re.findall(line)
                try:
                    transition_label = transition_label_re.search(line).group(1)
                except:
                    # pretty dot file
                    transition_label = ""
                    j += 1
                    while("</TABLE>>];" not in file_contents[j]):
                        transition_label += file_contents[j]  # assumes file is read with newlines left in place (fp.readlines(), not fp.read().splitlines())
                        j += 1
                    transition_label += file_contents[j].rstrip()[:-2]
                self.addTransition(state_labels[0], state_labels[1], transition_label)
                i = j
            elif state_re.search(line):
                state_label = state_re.search(line).group(1)
                self.addState(state_label)

    def generateDot(self, html = True, renumber_states = True):
        # does not insert newlines (except inside html labels), write with fp.writelines(map(lambda l: l + '\n', dot))
        dot = ['digraph g {',
            '__start0 [label="" shape="none"];',
            '']

        dot_alt = ['digraph g {',
            'rankdir="LR";',
            'graph [pad="0.5", ranksep="0.525", nodesep="3"];',
            '__start0 [label="" shape="none"];',
            '']

        for i in range(len(self.labels)):
            if renumber_states:
                state_label = str(i)
            else:
                state_label = self.labels[i]
            state_label = "\n".join(state_label.split("___"))
            dot.append('\t' + self.labels[i] + ' [shape="circle" label="' + state_label + '"];')

        for i in range(len(self.labels)):
            for j in range(len(self.transitions[i])):
                if html:
                    dot.append('\t' + self.labels[i] + ' -> ' + self.nexts[i][j] + ' [label=\n\t\t<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">\n' + self.transitions[i][j] + '\t\t</TABLE>>];')
                else:
                    dot.append('\t' + self.labels[i] + ' -> ' + self.nexts[i][j] + ' [label="' + self.transitions[i][j] + '"];')

        dot.append('')
        dot.append('__start0 -> s0;')
        dot.append('}')
        return dot
