#!/usr/bin/env bash

# process the profiling logs to generate traces for each transition
slime.trace simple_food_order_base/output/learnedModel.dot simple_food_order_base/logs/log.pickle Server
slime.trace simple_food_order_feat/output/learnedModel.dot simple_food_order_feat/logs/log.pickle Server
slime.trace simple_food_order_fix/output/learnedModel.dot simple_food_order_fix/logs/log.pickle Server
slime.trace uptane_preseed_wo_fix_trace/output/learnedModel.dot uptane_preseed_wo_fix_trace/logs/log.pickle Primary
slime.trace uptane_preseed_with_fix_trace/output/learnedModel.dot uptane_preseed_with_fix_trace/logs/log.pickle Primary

# generate 'pretty' models from the raw statelearner output (state names are arbitrary, did some manual relabeling for the paper and layout adjustments so things fit)
slime.pretty simple_food_order_base/output/learnedModel.dot --happy --paper simple_food_order_base/logs/output_alphabet_examples.json --acccolour 3 --rm-term
slime.pretty simple_food_order_feat/output/learnedModel.dot --happy --paper simple_food_order_feat/logs/output_alphabet_examples.json --acccolour 3 --rm-term
slime.pretty simple_food_order_fix/output/learnedModel.dot --happy --paper simple_food_order_fix/logs/output_alphabet_examples.json --acccolour 3 --rm-term
slime.pretty uptane_preseed_wo_fix/output/learnedModel.dot --rm s3 --happy --time uptane_preseed_wo_fix/logs/time_log.csv --paper uptane_preseed_wo_fix/logs/output_alphabet_examples.json --acccolour 4
slime.pretty uptane_preseed_with_fix/output/learnedModel.dot --rm s3 --happy --paper uptane_preseed_with_fix/logs/output_alphabet_examples.json --acccolour 4
slime.pretty uptane_preseed_wo_fix_trace/output/learnedModel.dot --rm-term --happy --paper uptane_preseed_wo_fix_trace/logs/output_alphabet_examples.json --acccolour 4
slime.pretty uptane_preseed_with_fix_trace/output/learnedModel.dot --rm-term --happy --paper uptane_preseed_with_fix_trace/logs/output_alphabet_examples.json --acccolour 4

# generate models annotated with the traces
slime.trace_stats simple_food_order_base/trace/state_summary/ --trace-type merge --dot simple_food_order_base/output/learnedModel_pretty.dot server.py
slime.trace_stats simple_food_order_feat/trace/state_summary/ --trace-type merge --dot simple_food_order_feat/output/learnedModel_pretty.dot server.py
slime.trace_stats simple_food_order_fix/trace/state_summary/ --trace-type merge --dot simple_food_order_fix/output/learnedModel_pretty.dot server.py
slime.trace_stats uptane_preseed_wo_fix_trace/trace/state_summary/ --trace-type merge --dot uptane_preseed_wo_fix_trace/output/learnedModel_pretty.dot /uptane/uptane/clients/primary.py
slime.trace_stats uptane_preseed_with_fix_trace/trace/state_summary/ --trace-type merge --dot uptane_preseed_with_fix_trace/output/learnedModel_pretty.dot /uptane/uptane/clients/primary.py

# rename states in a structured way using the happy path (state names are arbitrary, this algorithm is determinstic to make things consistent)
slime.states -d simple_food_order_base/output/learnedModel_pretty.dot -i
slime.states -d simple_food_order_feat/output/learnedModel_pretty.dot -i
slime.states -d simple_food_order_fix/output/learnedModel_pretty.dot -i
slime.states -d uptane_preseed_wo_fix/output/learnedModel_pretty.dot -i
slime.states -d uptane_preseed_with_fix/output/learnedModel_pretty.dot -i
slime.states -d uptane_preseed_wo_fix_trace/output/learnedModel_pretty.dot -i
slime.states -d uptane_preseed_with_fix_trace/output/learnedModel_pretty.dot -i

# generate models annotated with the traces with renamed states
slime.trace_stats simple_food_order_base/trace/state_summary/ --trace-type merge --dot simple_food_order_base/output/learnedModel_pretty_states.dot server.py --state-map simple_food_order_base/output/learnedModel_pretty_state_mapping.json
slime.trace_stats simple_food_order_feat/trace/state_summary/ --trace-type merge --dot simple_food_order_feat/output/learnedModel_pretty_states.dot server.py --state-map simple_food_order_feat/output/learnedModel_pretty_state_mapping.json
slime.trace_stats simple_food_order_fix/trace/state_summary/ --trace-type merge --dot simple_food_order_fix/output/learnedModel_pretty_states.dot server.py --state-map simple_food_order_fix/output/learnedModel_pretty_state_mapping.json
slime.trace_stats uptane_preseed_wo_fix_trace/trace/state_summary/ --trace-type merge --dot uptane_preseed_wo_fix_trace/output/learnedModel_pretty_states.dot /uptane/uptane/clients/primary.py --state-map uptane_preseed_wo_fix_trace/output/learnedModel_pretty_state_mapping.json
slime.trace_stats uptane_preseed_with_fix_trace/trace/state_summary/ --trace-type merge --dot uptane_preseed_with_fix_trace/output/learnedModel_pretty_states.dot /uptane/uptane/clients/primary.py --state-map uptane_preseed_with_fix_trace/output/learnedModel_pretty_state_mapping.json

# generate the diffs between models (this implementation of ltsdiff is non-determinstic with the generated dot file structure, so output may appear different and some runs may have really bad layouts, just run again)
cp simple_food_order_base/output/learnedModel.dot simple_food_order_base/output/learnedModel_f.dot
cp simple_food_order_feat/output/learnedModel.dot simple_food_order_feat/output/learnedModel_f.dot
cp simple_food_order_fix/output/learnedModel.dot simple_food_order_fix/output/learnedModel_f.dot
cp uptane_preseed_wo_fix_trace/output/learnedModel.dot uptane_preseed_wo_fix_trace/output/learnedModel_f.dot
cp uptane_preseed_with_fix_trace/output/learnedModel.dot uptane_preseed_with_fix_trace/output/learnedModel_f.dot
slime.diff --fix-dot simple_food_order_base/output/learnedModel_f.dot
slime.diff --fix-dot simple_food_order_feat/output/learnedModel_f.dot
slime.diff --fix-dot simple_food_order_fix/output/learnedModel_f.dot
slime.diff --fix-dot uptane_preseed_wo_fix_trace/output/learnedModel_f.dot
slime.diff --fix-dot uptane_preseed_with_fix_trace/output/learnedModel_f.dot
slime.diff --run simple_food_order_base/output/learnedModel_f.dot simple_food_order_feat/output/learnedModel_f.dot diffs/food_diff1.dot
slime.diff --run simple_food_order_feat/output/learnedModel_f.dot simple_food_order_fix/output/learnedModel_f.dot diffs/food_diff2.dot
slime.diff --run simple_food_order_base/output/learnedModel_f.dot simple_food_order_fix/output/learnedModel_f.dot diffs/food_diff3.dot
slime.diff --run uptane_preseed_wo_fix_trace/output/learnedModel_f.dot uptane_preseed_with_fix_trace/output/learnedModel_f.dot diffs/uptane_diff.dot
slime.diff --slime-format diffs/food_diff1.dot
slime.diff --slime-format diffs/food_diff2.dot
slime.diff --slime-format diffs/food_diff3.dot
slime.diff --slime-format diffs/uptane_diff.dot
slime.pretty diffs/food_diff1.dot --diff --rm-term --happy --paper simple_food_order_base/logs/output_alphabet_examples.json --acccolour 4
slime.pretty diffs/food_diff2.dot --diff --rm-term --happy --paper simple_food_order_base/logs/output_alphabet_examples.json --acccolour 4
slime.pretty diffs/food_diff3.dot --diff --rm-term --happy --paper simple_food_order_base/logs/output_alphabet_examples.json --acccolour 4
slime.pretty diffs/uptane_diff.dot --diff --rm-term --rm-noflow --happy --paper uptane_preseed_wo_fix_trace/logs/output_alphabet_examples.json --acccolour 4

# rename states in diffs
slime.states -d diffs/food_diff1_pretty.dot -i
slime.states -d diffs/food_diff2_pretty.dot -i
slime.states -d diffs/food_diff3_pretty.dot -i
slime.states -d diffs/uptane_diff_pretty.dot -i

