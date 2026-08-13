# macOS

This folder contains the macOS-specific installer and application bundle builder.

- `install.sh` installs the isolated Python runtime, dependencies, CLI launcher, and `.app` bundle.
- `build-app.sh` rebuilds the Finder-launchable `.app` bundle for an existing installation.

From the repository root, run:

```sh
./macos/install.sh
```

The app is installed at `~/Applications/Tihulu Star Trail.app` by default.
