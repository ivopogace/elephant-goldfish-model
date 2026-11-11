# Independent evaluation of the experimental OpenCode V2 adapter (#282)

This directory holds an outside check of the OpenCode V2 adapter proposed for
[google/elephant-goldfish-model#282](https://github.com/google/elephant-goldfish-model/issues/282):
candidate commit `b6c8913` on `Israel-Kli/elephant-goldfish-model`, OpenCode 2.2.6, and a
real model (LongCat 2.5 through OpenCode Go).

* [`REPORT.md`](REPORT.md): results against the acceptance criteria of #282.
* [`results/rerun-c72e2ef/`](results/rerun-c72e2ef) and
  [`results/rerun-c72e2ef-qwen/`](results/rerun-c72e2ef-qwen): the reruns on the author's fix
  commit with two models.
* [`results/limit-probes/`](results/limit-probes): probes of two limits the guide lists.
* [`results/campaign-quick-c72e2ef/`](results/campaign-quick-c72e2ef): a short repeat of the probes
  made with `campaign.py --quick`.
* [`results/agents-md-followed.md`](results/agents-md-followed.md): which reviews followed a
  planted rule and which only reported it.
* [`results/`](results): per-run analysis, the scripted operator's log, the files each
  workflow wrote, and sanitized traces.
* [`harness/`](harness): the scripts that produced the results.
* [`video/`](video): the scripts, narration and subtitles for the narrated video of one run
  (`results/brainstorm-2-video`). The rendered MP4 is not stored in the repository.
* [`run_all.sh`](run_all.sh): repeats everything.

It is evaluation material, not part of the adapter. It changes nothing under `skills/`,
`agents/` or `adapters/`.

## How a run works

```
           disposable profile (HOME, XDG config/cache/state)        fake project "lendr"
                              |                                            |
 driver.py --HTTP API--> opencode serve (candidate opencode.json) --tools--+
     |                        |
     | answers gates,         | model requests
     | chat turns and         v
     | permission asks   capture_proxy.py --HTTPS--> OpenCode Go (LongCat 2.5)
     v                        |
 operator.jsonl          provider-requests.jsonl        sessions/*.json (API export)
```

1. `fixture.py` builds a project and a profile that contain only invented data. It plants a
   different random marker in each place an instruction or a secret could leak from: the
   global, project and nested `AGENTS.md`, a configured instruction file, the operator's
   prompt, a fake `.env`, and a file outside the project (both also reachable through
   symlinks in the project).
2. `driver.py` starts a private OpenCode server with the candidate configuration and plays
   the operator through the HTTP API. What it says is fixed text in `workflows.py`. It
   holds every gate open for six seconds before answering, and answers permission requests
   from a short allowlist (document writes inside the project, `git config user.name`).
3. `capture_proxy.py` sits between OpenCode and the model and records every request body
   and reassembled response. Headers, which carry the login, are forwarded but not stored.
4. `analyze.py` turns the three records of a run into named checks; `summarize.py` puts
   several runs in one table.

No person sat at the gates in the reported runs. The report says where that limits what
was verified.

### A person at the gates

`--human` hands every gate and every chat turn to a person and waits. Permission requests
still follow the fixed allowlist. Waiting time does not count against `--timeout`.

```sh
python3 harness/driver.py review --human --output /absolute/new/run/dir
```

Started from a terminal, the driver prints each question and reads the answer. Started
without one, it writes `pending.json` in the run directory and waits; answer from another
shell:

```sh
python3 harness/answer.py /absolute/new/run/dir            # show the question
python3 harness/answer.py /absolute/new/run/dir 1          # choose option 1
python3 harness/answer.py /absolute/new/run/dir "my words" # write-in, or a chat reply
```

`cancel` dismisses a gate, `default` sends the scripted chat reply, `end` stops the run.
The analysis then reports `gates_answered_by_a_person`.

## One command for a candidate commit

`harness/campaign.py` does the whole sequence for any commit: check it out, install and
verify it, run the candidate's unit tests and scripted probe, find each model's endpoint
and check that it answers, run the live runs (and the same probes on an older install as a
control), analyze, and print a summary table.

```sh
python3 harness/campaign.py \
  --source /absolute/checkout/of/the/fork --commit <sha> \
  --output /absolute/new/dir \
  --model opencode-go/deepseek-v4.1-flash --model opencode-go/qwen3.8-flash \
  --control-install /absolute/older/install \
  --export results/<name>
```

* `--quick` runs only the short probes (symlink read, `grep`, a design that links to
  `AGENTS.md`, a design that links to another file with a planted rule). Minutes, not an hour.
* `--resume` continues in the same output directory after an interruption. Finished runs are
  kept; a run that was cut off is started again.
* `--human` runs brainstorm, draft and review in sequence with a person answering every gate,
  instead of the scripted runs.
* A model that returns no successful answer (rate limited, not offered) is reported and
  skipped; the others still run.
* The table is also written to `<output>/comment-table.md`.

## Repeat it

Requirements: Python 3.10+, OpenCode 2.2.6, the candidate installed with
`adapters/opencode/install.py --interface v2`, a checkout of the candidate commit, and an
OpenCode login that can use the model (`opencode auth login`). For the video: `tmux`,
`asciinema`, `ffmpeg`, `espeak-ng`, Kokoro-82M ONNX with the `af_heart` voice, and the
Python packages `pyte`, `Pillow`, `numpy` and `onnxruntime`.

```sh
./run_all.sh /absolute/new/output/dir /absolute/checkout/of/b6c8913
```

One workflow at a time:

```sh
python3 harness/driver.py brainstorm --output /absolute/new/run/dir
python3 harness/driver.py draft  --project-from /absolute/brainstorm/run --output /absolute/draft/run
python3 harness/driver.py review --project-from /absolute/draft/run --output /absolute/review/run
python3 harness/analyze.py /absolute/run/dir
```

The video:

```sh
python3 harness/driver.py brainstorm --record-tui --preapprove-writes --output /absolute/demo/run
python3 video/make_video.py --run /absolute/demo/run --narration video/narration.json \
  --output /absolute/egm-opencode-v2-run.mp4 --work /absolute/scratch/dir
```

Model output differs between runs, so counts will not match exactly. The checks are written
to hold for any run.

## What is and is not in `results/`

Kept: `analysis.json`, `operator.jsonl`, the written artifacts, and xz-compressed
`provider-requests.jsonl` and session exports (`xz -dc file.xz`). `sanitize.py` replaces
local paths and organisation identifiers, drops billing details, and refuses to write if a
credential-like string remains.

Not kept, and never to be added: OpenCode's database, its auth files, and server logs.
The login stays in the machine's own OpenCode data directory, which the harness uses in
place and does not copy.
