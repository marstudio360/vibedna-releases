# Vibedna releases: the public record

This repository is the public record of the tools Vibedna publishes at https://vibedna.ai. It exists so that you, or the AI
that installs a tool for you, can check a download against a second place that is not the page you got it from.

What is here:

- `checksums.txt`: the SHA-256 of every current download, one per line (`<sha256>  <file name>`).
- `manifests/<file name>.sha256`: the SHA-256 of every file inside that zip, so you can check the unzipped folder too.
- `guides/`: the install guide of each tool, the same text that is served at `https://vibedna.ai/installs/<tool>.md`.
- `source/<tool>/`: the full code of the tools that are free in the store, exactly as it is inside the zip.

Every change is a commit, so the history shows when a checksum was published and that it was not changed afterwards.

## How to check a download

1. Get the file from your library at https://vibedna.ai/library.
2. Compute its SHA-256. Linux: `sha256sum <file>`. macOS: `shasum -a 256 <file>`. Windows PowerShell: `Get-FileHash <file>`.
3. Find the file name in `checksums.txt`. The two values must be equal. If they differ, do not install it and write to admin@vibedna.ai.
4. After unzipping you can check each file against `manifests/<file name>.sha256` the same way.

## What this does and does not prove

It proves that the file you have is the file we published, and that we did not swap it later without a visible commit.
It does not prove that the code is safe: for the free tools you can read the code here before you install anything; for the
paid tools, read the code in your own copy first, which is what each install guide asks your AI to do.

## Current downloads

| Tool | File | Bytes | Files | Source here |
|---|---|---|---|---|
| ai-company-system | `ai-company-system-1.0.1.zip` | 319,761 | 87 | no (paid tool): checksums and file list only |
| content-studio | `social-content-studio-mcp-1.3.6.zip` | 94,938 | 10 | yes, in `source/content-studio/` |
| cover-studio | `cover-studio-mcp-1.1.3.zip` | 62,865 | 10 | no (paid tool): checksums and file list only |
| ebook-forge | `ebook-forge-mcp-1.2.2.zip` | 224,208 | 61 | no (paid tool): checksums and file list only |
| ebook-system | `Ebook-System-1.2.2.zip` | 249,234 | 63 | no (paid tool): checksums and file list only |
| game-assets | `game-assets-mcp-1.0.5.zip` | 60,132 | 14 | yes, in `source/game-assets/` |
| godot | `godot-vibe-mcp-1.1.5.zip` | 61,778 | 5 | no (paid tool): checksums and file list only |
| google-ads | `google-ads-dna-1.0.3.zip` | 16,420 | 4 | no (paid tool): checksums and file list only |
| gumroad | `gumroad-dna-2.3.2.zip` | 23,655 | 11 | yes, in `source/gumroad/` |
| jester | `jester-mcp-1.0.5.zip` | 161,599 | 53 | no (paid tool): checksums and file list only |
| social-brain | `social-brain-mcp-1.11.18.zip` | 451,734 | 31 | no (paid tool): checksums and file list only |
| unity | `unity-vibe-mcp-1.0.3.zip` | 36,780 | 4 | no (paid tool): checksums and file list only |
| unreal | `unreal-vibe-mcp-1.0.3.zip` | 27,660 | 4 | no (paid tool): checksums and file list only |
| vault | `vault-mcp-1.1.4.zip` | 24,811 | 9 | yes, in `source/vault/` |
| vibegen | `vibegen-mcp-1.1.2.zip` | 15,596 | 4 | yes, in `source/vibegen/` |
| youtubedna | `youtubedna-mcp-1.0.6.zip` | 30,660 | 5 | no (paid tool): checksums and file list only |

Support: admin@vibedna.ai
