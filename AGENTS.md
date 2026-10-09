# Local preview and production

The shared local checkout is `D:/PROMETEO`. Its Django server runs from
`D:/PROMETEO/webapp` at `http://127.0.0.1:8000`, using
`D:/PROMETEO/elgranextractor/venv/Scripts/python.exe`.

For application changes, preparing a working local preview is part of the task.
Do not leave finished changes only in a Codex worktree. First compare the shared
checkout with `origin/main`, preserve existing local edits, and integrate the
requested changes into the checkout that the local server actually serves.
Verify the page and its static assets through the local HTTP endpoint.

The user wants to try changes locally before deciding whether to deploy. Keep
production unchanged until the user explicitly asks to publish. On deployment,
integrate with the latest production revision, preserve other work, and verify
the public page and static assets before reporting success.

Do not describe all environments as synchronized when local changes remain
unpublished. State clearly which changes are ready locally and which are live.
