# Forge Desktop

This folder is the downloadable desktop shell for Forge.

The desktop app wraps the local Next.js UI and talks to the local FastAPI gateway. In production packaging, the installer should start the gateway, worker, and web assets as sidecar processes, then open the Tauri window to the local UI.

Target platforms:

- Windows
- macOS
- Linux

Safety contract:

- A project folder must be selected before agent work starts.
- Tauri folder selection passes the absolute folder path to `/api/projects/select`.
- All file reads and approved writes go through the gateway workspace validator.
- AI patches are staged and shown as diffs before any save.
