# Contributing

This is a solo hackathon submission for the CockroachDB × AWS Hackathon 2026, built within the official Submission Period (June 30 – Aug 18, 2026). External contributions during that window won't be merged, to keep the submission's authorship unambiguous per the hackathon's IP/originality rules.

After the hackathon judging period concludes, this note will be updated and the project opened to normal contribution flow (issues, PRs, discussion).

## Local development
```bash
git clone https://github.com/iarjunganesh/continuum.git
cd continuum
pip install -r requirements.txt
cp .env.example .env   # fill in CockroachDB + AWS credentials
make migrate
make seed-data
```

## Before opening an issue
Check `docs/adr/` — a number of "why isn't X included" questions are already answered there as deliberate scope decisions, not oversights.
