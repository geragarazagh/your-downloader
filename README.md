<img src="assets/icon.png" width="128" alt="youtube-download icon: a play sign turned down onto a line">

# youtube-download: a skill for AI assistants that takes everything yt-dlp can from a video page

A free, open source agent skill around [yt-dlp](https://github.com/yt-dlp/yt-dlp). Paste a link and say what to keep: «save this for my iPhone», «only the audio as mp3», «the first ten videos of this playlist», «with English subtitles», «from 1:30 to 2:45», «what is this video about», «what do people say in the comments». The assistant runs yt-dlp on the computer, checks the file, and says what it saved.

- Video that plays everywhere (H.264 and AAC in mp4: phones, iPhone, TVs, QuickTime), a smaller copy, or the highest quality up to 4K.
- Only the sound as m4a (copied, no quality lost) or mp3, with the cover picture.
- Subtitles inside the video or as an .srt file; YouTube's automatic captions in the spoken language, never a machine translation unless asked.
- A text file of the video: title, channel, date, views, description, chapters and the whole transcript with times, for reading or for the assistant to summarise.
- Comments: the most liked or the newest threads with their replies, in the same text file.
- The thumbnail as a JPEG, a part of a video by time, sponsor segments cut out (SponsorBlock), another audio language of a dubbed video.
- Playlists and channels, numbered in a folder; only the new videos on later runs.
- YouTube, YouTube Music, Vimeo, SoundCloud, Bandcamp, Twitch, Reddit, X, TikTok, Instagram, Facebook, Bilibili, the Internet Archive and about 1,700 other sites.

Works in assistants that run commands on the person's own computer with internet access: terminal agents such as Claude Code, Codex, Gemini CLI and Antigravity, OpenCode, OpenClaw, Hermes and others. Chat apps cannot do it: their sandboxes cannot reach video sites, and there the skill says so instead of pretending. `SKILL.md` carries the whole method and can be pasted into any agent as instructions; one small script, `scripts/read_video.py` (Python standard library), turns a video's captions and comments into readable text, and the skill says how to do the same without it.

## Install

Each way is marked by how it was checked: **run** means installed and used for real on the date in «Tested on»; **docs** means taken from the vendor's documentation on 2026-11-15 and not yet run.

### The tools it needs

yt-dlp, ffmpeg, and for YouTube a JavaScript runtime, deno (since version 2025.11.12 yt-dlp needs an external JavaScript runtime to answer YouTube's challenges); Python 3.8 or newer for the text script. The assistant checks for them and, when one is missing, names the command and waits for a yes:

- macOS: `brew install yt-dlp ffmpeg` (Homebrew's yt-dlp brings deno).
- Windows: `winget install yt-dlp.yt-dlp` (brings ffmpeg and deno).
- Linux: `pipx install "yt-dlp[default]"`, ffmpeg from the system's package manager, deno from [deno.com](https://docs.deno.com/runtime/getting_started/installation/). The yt-dlp in most distributions' own repositories is too old for YouTube.

### Terminal agents

One command for every agent found on the computer (needs Node.js; `-g` installs for the user, without it for the current project only) — **run**:

```sh
npx skills add geragarazagh/youtube-download -g
```

It puts the skill into `~/.agents/skills/youtube-download`, which Codex, Cursor, Cline, OpenCode and most other agents read, and links it into `~/.claude/skills` for Claude Code.

Claude Code, as a plugin — **run**:

```sh
claude plugin marketplace add geragarazagh/youtube-download
claude plugin install youtube-download@youtube-download
```

By hand, any agent that reads the Agent Skills folder (Codex, OpenCode, OpenClaw, Hermes, Grok Build) — **docs**: copy the folder `skills/youtube-download` (with `scripts/` inside) to `~/.agents/skills/youtube-download`. Claude Code reads `~/.claude/skills/youtube-download`; Antigravity reads `~/.gemini/config/skills/youtube-download`.

### No skills in the agent

Paste the text of [`SKILL.md`](skills/youtube-download/SKILL.md) into the agent's instructions (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md` or the agent's settings), or as the first message of a session. Downloads work the same; for transcripts and comments the agent then uses the commands the skill gives for working without the script.

## Use

Paste a link and say what you want, in any language. To call the skill by name: `/youtube-download` in Claude Code (`/youtube-download:youtube-download` when installed as the plugin) and Antigravity; `$youtube-download` in Codex.

```
Download this so it plays on my iPhone: https://www.youtube.com/watch?v=…
Save only the sound of this video as mp3.
Download the first five videos of this playlist, audio only.
Download it with English subtitles inside.
Cut out 1:30 to 2:45 of this video.
What is this video about? And what do the top comments say?
Save the thumbnail of this video.
```

The assistant answers in the language of the request and starts at once when the link and the wish are clear. Files go to the Downloads folder unless the request names another place; a playlist goes into a folder of its own, numbered. It asks only when the link or the wish is missing, before using automatic captions or a machine translation, before using a browser login, and before switching yt-dlp to its nightly build.

## What this skill does on the computer

- Runs yt-dlp, ffmpeg and ffprobe on the link in the request, and `scripts/read_video.py`, which itself only runs yt-dlp and writes one text file. yt-dlp runs YouTube's challenge scripts in deno with no file or network access (yt-dlp's own design).
- Connects only to the site of the link, and to SponsorBlock's public API (sponsor.ajay.app) only when the person asks to cut sponsor segments. Sends nothing else anywhere: no telemetry, no accounts, no keys.
- Writes only the downloaded files and text files, in Downloads or where the person said; a text file made only for the assistant to read goes to a temporary folder and is deleted. Never deletes or overwrites a file of the person's without asking.
- Installs and updates nothing by itself: names the command and waits for a yes.
- Reads the browser's cookies only after the person agrees, for a video that needs their login (age-restricted, private, members-only). Never asks for a password, never saves cookies.
- Stores nothing about the person. Anything they answer lives only in the conversation.
- The installers are other people's programs with their own rules: `npx skills` (Vercel) sends an anonymous install count unless `DISABLE_TELEMETRY=1` is set.

## Tested on

2026-11-16, in a fresh Claude Code configuration (its own login, no user instructions, only this skill and two others of the same author (text to speech, audiobooks), so that a near miss could start the wrong one): Claude Haiku 5.5 (`claude-haiku-5-5`) in Claude Code 2.1.325 on macOS 27.2 (Apple M3 Pro), with yt-dlp 2026.10.26 (Homebrew), ffmpeg 9.0.2 and deno 2.9.8. Real requests; every file checked with ffprobe:

- «Download this so it plays on my iPhone» with a Creative Commons video from NASA's YouTube channel: H.264 1080p and AAC in mp4, the full length, title, author and date inside.
- «Сохрани только звук…» (Russian, the same video): AAC copied without re-encoding into m4a, with the cover; the answer in Russian.
- «What is this video about, and what do the most liked comments say?» on «Me at the zoo»: the text script, comment threads read from a temporary folder; the answer matched the file.
- A bare `/youtube-download` with no link: one question, nothing downloaded.
- The skill started by itself for all three plain requests, and for none of three near misses (an mp3 to m4a, a transcription of a local recording, the sound out of a local mp4).

2026-11-15, the first draft (video, sound, playlist, subtitles, 4K, the Internet Archive, a Vimeo link that needs a login): 8 of 8 downloads right; the same requests without the skill downloaded too, with weaker files (no chapters or metadata, the sound re-encoded from Opus at twice the size, 4K as VP9 and Opus in MKV, which iPhones and QuickTime do not play).

Installs from this repository, the same day: `npx skills add geragarazagh/youtube-download -g` into an empty home folder (files identical to the repository, linked for Claude Code and Antigravity), and the Claude Code plugin commands above, then «save only the sound of this video as mp3» through `/youtube-download:youtube-download` on Haiku 5.5 (an mp3 with the cover, the full length).

Every command in `SKILL.md` was run on 2026-11-16 on the setup above. On 2026-11-17 the latest stable yt-dlp was still 2026.10.26; with it, «Me at the zoo» downloaded for an iPhone as H.264 and AAC in mp4, 19 s, the full length. Not tested: other models, other agents, Linux and Windows.

## What it cannot do

- Run in a chat app: the sandbox cannot reach video sites.
- DRM-protected video (Netflix, Disney+, paid films on YouTube), paywalls, memberships the person does not have.
- Turn speech into text where a video has no captions: that needs a speech-to-text tool.
- Guarantee YouTube: YouTube changes often and yt-dlp catches up within days. When downloads start failing, update yt-dlp; the skill says how.

## Downloading and the law

Downloading may break a site's terms. YouTube's Terms of Service forbid downloading content without permission from YouTube or the rights holders, except where YouTube itself offers a download. Copyright law differs from country to country. The skill downloads what the person asks for and leaves that judgement to them; it does not get around DRM or paywalls. Fine to download: your own videos, public-domain and Creative Commons works, and what the rights holder allows.

## License

MIT
