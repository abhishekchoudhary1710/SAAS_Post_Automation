# Working on this from another PC

The posts are made on GitHub, so nothing here is needed for them to keep going. This is for
editing the agent and testing it locally.

## Once

1. Install Python 3.12 or newer and Git.
2. `git clone https://github.com/abhishekchoudhary1710/SAAS_Post_Automation.git`
3. In the folder: `pip install -r requirements.txt`
   ffmpeg, fonts and brand images come with the packages and the repo.
4. Copy `.env` from the first PC into the folder. It is ignored by git on purpose. Without it,
   `create` works (renders a video) but `publish` and `verify` cannot reach the accounts.
   If the file is lost, `.env.example` lists every key and `setup/` has the scripts that mint
   the Meta and YouTube tokens again.
5. Optional, for Claude Code: it reads `CLAUDE.md` automatically. Nothing else to copy.

## What behaves differently locally

- **Voice.** The human voices need Google credentials that exist only on GitHub (keyless
  Workload Identity). Locally the chain falls back to the Edge voice. Published videos are
  unaffected.
- **Footage.** Veo needs the same credentials. Local builds use the card fallback unless you set
  `VEO_ENABLED=false` explicitly to skip the attempt, or configure Application Default
  Credentials for project `video-generation-uniyal`.
- **Gemini free tier quotas are per key, shared with GitHub.** The text models are generous; the
  TTS model allows 10 calls a day. Do not run voice tests on a posting day.

## Useful commands

```
python -m agent verify                 # every credential and dependency, green or red
python -m agent create --format film   # build one film into out/<timestamp>-film, publish nothing
python -m agent publish out/<folder>   # publish a built folder to the platforms in PLATFORMS
```

## Do not

- `git add -A`. Stage named files. The repo is public.
- Paste tokens into any chat. If one leaks, rotate it.
