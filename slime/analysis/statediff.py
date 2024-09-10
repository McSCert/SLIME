import argparse
import os
import subprocess
import sys

# wrapper which clones and patches an implementation of the LTSDiff algorithm from https://github.com/GianniM123/ResearchInternship
# paper: Automated Comparison of State-Based Software Models in terms of their Language and Structure - Neil Walkinshaw, and Kirill Bogdanov https://www.cs.le.ac.uk/people/nwalkinshaw/Files/tosem2012.pdf

PATCH = r"""diff --git a/algorithm/requirements.txt b/algorithm/requirements.txt
index 3602eaf..3f97c3d 100644
--- a/algorithm/requirements.txt
+++ b/algorithm/requirements.txt
@@ -1,4 +1,4 @@
 networkx
 pysmt
 graphviz
-pygraphviz
\ No newline at end of file
+pygraphviz
diff --git a/dockerfile b/dockerfile
index 37991d9..88f4df3 100644
--- a/dockerfile
+++ b/dockerfile
@@ -1,13 +1,12 @@
-FROM ubuntu:20.04
+FROM ubuntu:22.04
 
 ENV DEBIAN_FRONTEND=noninteractive
 
 RUN apt-get update && \
-    apt-get install -y python3-pip python3-dev pkg-config graphviz-dev \
+    apt-get install -y python3-pip python3-dev python3-numpy python3-pygraphviz python3-pydot python3-scipy libumfpack5 pkg-config graphviz-dev \
     swig libgmp-dev autoconf libtool antlr3 wget curl gperf
 
-RUN /usr/bin/python3 -m pip install --upgrade pip && \
-    pip install pygraphviz && pip install scikit-umfpack && pip install pydot
+RUN /usr/bin/python3 -m pip install --upgrade pip
 
 
 
"""

def state_diff(in1, in2, output_file, *args):
    directory_in1 = os.path.dirname(os.path.abspath(in1))
    directory_in2 = os.path.dirname(os.path.abspath(in2))
    directory_out = os.path.dirname(os.path.abspath(output_file))
    fname_in1 = os.path.basename(in1)
    fname_in2 = os.path.basename(in2)
    fname_out = os.path.basename(output_file)
    volume_mounts = ["-v", f"{directory_in1}:/in1", "-v", f"{directory_in2}:/in2", "-v", f"{directory_out}:/out"]
    ltsdiff_command = ["python3", "main.py", "--ref=/in1/" + fname_in1, "--upd=/in2/" + fname_in2, "-o", "/out/" + fname_out]
    subprocess.run(["sudo", "docker", "run", "-it", "-a", "stdout", "--rm"] + volume_mounts +  ["ltsdiff"] + ltsdiff_command + [*args])
    subprocess.run(["sudo", "chown", f"{os.getuid()}:{os.getgid()}", output_file])

def fix_dot_file(dot_file):
    directory_dot = os.path.dirname(os.path.abspath(dot_file))
    fname_dot = os.path.basename(dot_file)
    volume_mounts = ["-v", f"{directory_dot}:/cwd"]
    ltsdiff_command = ["python3", "/code/dot-files/fix-dot-files.py", "/cwd/" + fname_dot]
    subprocess.run(["sudo", "docker", "run", "-it", "-a", "stdout", "--rm"] + volume_mounts +  ["ltsdiff"] + ltsdiff_command)

def clone_and_patch():
    assert not os.path.exists("ResearchInternship")
    assert not os.path.exists("LTSDiff")
    subprocess.run(["git", "clone", "https://github.com/GianniM123/ResearchInternship.git"])
    os.rename("ResearchInternship", "LTSDiff")
    os.chdir("LTSDiff")
    subprocess.run(["git", "apply", "-"], input=PATCH, encoding="utf-8")

def build_docker_image():
    if not os.path.exists("dockerfile"):
        assert os.path.exists("LTSDiff")
        os.chdir("LTSDiff")
    assert os.path.exists("dockerfile")
    subprocess.run(["sudo", "docker", "build", "-t", "ltsdiff", "."])

def slime_format(dot_file: str):
    # read dot file
    with open(dot_file, "r") as f:
        lines = f.readlines()
    # remove first line and last line
    lines = lines[1:-1]
    # keep track of state renames with dictionary
    state_renames = {}
    # keep track of transitions with a list of tuples
    transitions = []
    # keep list of new states
    new_states = []
    # keep list of removed states
    removed_states = []
    # current transition and label
    current_transition = ""
    current_label = ""
    # iterate over lines to find start state which has a self loop (should only be one), this state will be removed and the real first (initial) state is the next one
    fake_first_state = ""
    real_first_state = ""
    for line in lines:
        if "->" in line:
            source, target = line.strip().split("->")
            source = source.strip()
            target = target.strip().split()[0]
            current_transition = " -> ".join([source, target])
        elif "Self loop" in line:
            fake_first_state = current_transition.split(" -> ")[0]
            break
    for line in lines:
        if "->" in line:
            source, target = line.strip().split("->")
            source = source.strip()
            target = target.strip().split()[0]
            if source == fake_first_state and target != fake_first_state:
                real_first_state = target
                state_renames[real_first_state] = f"s{len(state_renames)}"
                break
    # iterate over lines
    current_transition = ""
    current_label = ""
    for line in lines:
        if "->" in line:
            # transition line
            if current_transition and current_label:
                transitions.append((current_transition, current_label))
                current_transition = ""
                current_label = ""
            source, target = line.strip().split("->")
            source = source.strip()
            target = target.strip().split()[0]
            if source == fake_first_state:
                # don't add fake first state (with self loop) (had a case with multiple but still only 1 self loop)
                continue
            if source not in state_renames:
                state_renames[source] = f"s{len(state_renames)}"
            if target not in state_renames:
                state_renames[target] = f"s{len(state_renames)}"
            source = state_renames[source]
            target = state_renames[target]
            current_transition = " -> ".join([source, target])
        elif "Self loop" in line:
            continue
        elif line.strip().startswith("label="):
            # label line (for transitions)
            label = line.strip().split("=")[1]
            current_label = current_label + label.strip("\"];")
        elif line.strip().startswith("color="):
            # color line (for transitions)
            color = line.strip().split("=")[1]
            if color == "red,":
                current_label = "REM" + current_label
            elif color == "green,":
                current_label = "ADD" + current_label
        elif "color" in line:
            # state line
            state = line.strip().split()[0]
            if state not in state_renames:
                state_renames[state] = f"s{len(state_renames)}"
            state = state_renames[state]
            if "red" in line:
                removed_states.append(state)
            elif "green" in line:
                new_states.append(state)
        else:
            # error
            raise ValueError(f"Unknown line: {line}")
    # add last transition
    if current_transition and current_label:
        transitions.append((current_transition, current_label))
    # create new dot file
    new_dot_file = ["digraph G {", '__start0 [label="" shape="none"];', ""]
    for state in range(len(state_renames)):
        if f"s{state}" in new_states:
            new_dot_file.append(f"\ts{state} [shape=\"circle\" label=\"{state}\" color=green];")
        elif f"s{state}" in removed_states:
            new_dot_file.append(f"\ts{state} [shape=\"circle\" label=\"{state}\" color=red];")
        else:
            new_dot_file.append(f"\ts{state} [shape=\"circle\" label=\"{state}\"];")
    for transition, label in transitions:
        new_dot_file.append(f"\t{transition} [label=\"{label}\"];")
    new_dot_file.append("")
    new_dot_file.append("__start0 -> s0;")
    new_dot_file.append("}")
    # write new dot file
    with open(dot_file, "w") as f:
        f.write("\n".join(new_dot_file))


def main() -> int:
    parser = argparse.ArgumentParser(description = "Wrapper for LTSDiff algorithm")
    parser.add_argument("--clone", action="store_true", help="clone and patch LTSDiff algorithm")
    parser.add_argument("--build", action="store_true", help="build docker image for LTSDiff algorithm")
    parser.add_argument("--fix-dot", action="store", type=str, metavar="DOT", help="fix dot file for diffing algorithm, overwrites dot file")
    parser.add_argument("--run", action="store", nargs=3, metavar=("IN1", "IN2", "OUT"), help="run LTSDiff on IN1 and IN2, output to OUT (!overwrites all files!)")
    parser.add_argument("--fix-and-run", action="store", nargs=3, metavar=("IN1", "IN2", "OUT"), help="fix and run files all at once")
    parser.add_argument(nargs=argparse.REMAINDER, dest="extra_args", help="extra arguments for LTSDiff algorithm (separate with -- ): -l (add logging in out file) -d (print smt) -e (print linear equation output) -i (print time smt takes) -p (performance matrix) -s <smt-solver> -k <k value> -t <threshold value> -r <ratio value>")
    parser.add_argument("--slime-format", action="store", type=str, metavar="DOT", help="convert output dot file back to slime format (for the analysis spaghetti code)")
    args = parser.parse_args()

    if args.clone:
        clone_and_patch()
    if args.build:
        build_docker_image()
    if args.fix_dot:
        fix_dot_file(args.fix_dot)
    if args.run:
        state_diff(*args.run, *args.extra_args)
    if args.fix_and_run:
        fix_dot_file(args.fix_and_run[0])
        fix_dot_file(args.fix_and_run[1])
        state_diff(*args.fix_and_run, *args.extra_args)
    if args.slime_format:
        slime_format(args.slime_format)

    return 0

if __name__ == "__main__":
    sys.exit(main())

