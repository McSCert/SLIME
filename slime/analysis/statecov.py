import pickle
import sys
import os
import code
import subprocess
import time
from simplestatemachine import StateMachine
from covparser import Coverage

def start_container():
    cmd_start = ["sudo", "podman", "run", "--name", "covgenhtml", "-it", "aktualizr_client2"]
    subprocess.run(cmd_start)

def get_html_cov(lcov):
    # todo: integrate with sutctrl and slime main
    cmd_cov_push = ["sudo", "podman", "cp", "fsmhtml/" + lcov, "covgenhtml:/home/aktualizr/build/"]
    cmd_cov_pull = ["sudo", "podman", "cp", "covgenhtml:/home/aktualizr/build/html", os.path.join(os.getcwd(), "fsmhtml", os.path.splitext(lcov)[0])]
    cmd_cov_html = ["sudo", "podman", "exec", "covgenhtml", "genhtml", "-q", "-o", "/home/aktualizr/build/html", os.path.join("/home/aktualizr/build/", lcov)]
    subprocess.run(cmd_cov_push)
    subprocess.run(cmd_cov_html)
    time.sleep(0.5)
    subprocess.run(cmd_cov_pull)

droppedFile = sys.argv[1]
droppedFile = droppedFile.replace(os.path.sep, '/')
if os.path.splitext(droppedFile)[1] == ".dot":
    fsmdot = droppedFile
else:
    sys.exit()
# fsmdot = "../../output/learnedModel.dot"
slimepickle = "../logs/log.pickle"

slimelog = []
with open(slimepickle, "rb") as f:
    try:
        while True:
            slimelog.append(pickle.load(f))
    except:
        pass

with open(fsmdot, "r") as f:
    fsmdot = f.readlines()

print("Stage 1: Load model and log")
fsm = StateMachine()
fsm.readDotFile(fsmdot)

print("Stage 2: Add coverage to fsm")
l = 1
last_cov = ""
try:
    for entry in slimelog:
        cmds = entry["cmd"][0].split(";")
        res = entry["res"][0].split(";")
        cov_str = pickle.loads(eval(entry["cov"][0]))
        print(last_cov == cov_str)
        last_cov = cov_str
        with open("cov/" + str(l) + "-orig.info", "w") as f:
            f.write(cov_str)
        cov = Coverage(cov_str, "lcov")
        # cov.write("cov/" + str(l) + ".info")
        t = []
        for i in range(len(cmds)):
            t.append(cmds[i] + " / " + res[i])
        if fsm.addCoverage(t, cov):
            pass
            # print("Pass " + str(t))
        else:
            print("ERROR LINE: " + str(l))
        l += 1
except:
    print("EXCEPTION LINE: " + str(l))

print("Stage 3: Get min and max coverage for each state")
for i in range(len(fsm.labels)):
    state_cov = fsm.coverage_data[i]
    if state_cov:
        max_cov = state_cov[0]
        min_cov = state_cov[0]
        for cov in state_cov[1:]:
            max_cov = max_cov | cov
            min_cov = min_cov & cov
        fsm.coverage_data[i] = [min_cov, max_cov]
        fsm.coverage_data[i][0].write("fsmhtml/" + fsm.labels[i] + "_min.info")
        fsm.coverage_data[i][1].write("fsmhtml/" + fsm.labels[i] + "_max.info")
        # get_html_cov(fsm.labels[i] + "_min.info")
        # get_html_cov(fsm.labels[i] + "_max.info")

code.interact(local=locals())
