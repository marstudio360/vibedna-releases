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
| ai-company-system | `ai-company-system-1.0.2.zip` | 325,517 | 88 | no (paid tool): checksums and file list only |
| content-studio | `social-content-studio-mcp-1.3.7.zip` | 102,701 | 11 | yes, in `source/content-studio/` |
| cover-studio | `cover-studio-mcp-1.1.4.zip` | 71,018 | 12 | no (paid tool): checksums and file list only |
| ebook-forge | `ebook-forge-mcp-1.2.3.zip` | 229,369 | 62 | no (paid tool): checksums and file list only |
| ebook-system | `Ebook-System-1.2.3.zip` | 254,661 | 64 | no (paid tool): checksums and file list only |
| game-assets | `game-assets-mcp-1.0.6.zip` | 61,803 | 15 | yes, in `source/game-assets/` |
| godot | `godot-vibe-mcp-1.1.6.zip` | 64,608 | 6 | no (paid tool): checksums and file list only |
| google-ads | `google-ads-dna-1.0.5.zip` | 19,443 | 5 | no (paid tool): checksums and file list only |
| gumroad | `gumroad-dna-2.3.3.zip` | 26,087 | 12 | yes, in `source/gumroad/` |
| jester | `jester-mcp-1.0.7.zip` | 165,210 | 54 | no (paid tool): checksums and file list only |
| social-brain | `social-brain-mcp-1.12.2.zip` | 634,339 | 38 | no (paid tool): checksums and file list only |
| spotify-manager | `spotify-manager-mcp-1.2.3.zip` | 49,237 | 10 | no (paid tool): checksums and file list only |
| unity | `unity-vibe-mcp-1.0.4.zip` | 38,763 | 5 | no (paid tool): checksums and file list only |
| unreal | `unreal-vibe-mcp-1.0.4.zip` | 29,708 | 5 | no (paid tool): checksums and file list only |
| vault | `vault-mcp-1.1.5.zip` | 27,117 | 10 | yes, in `source/vault/` |
| vibegen | `vibegen-mcp-1.1.3.zip` | 18,389 | 5 | yes, in `source/vibegen/` |
| viz-studio | `viz-studio-mcp-1.1.3.zip` | 32,639 | 7 | no (paid tool): checksums and file list only |
| youtubedna | `youtubedna-mcp-1.0.7.zip` | 33,124 | 6 | no (paid tool): checksums and file list only |

Support: admin@vibedna.ai
