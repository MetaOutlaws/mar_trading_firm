# Dashboard git sha (container has no .git)

`GET /api/desk` shows the deployed commit in the header. The SGP1 image does
not contain a `.git` directory, so `git rev-parse` cannot see HEAD and the
field stays null (`source: unavailable`) until deploy stamps the sha another
way.

Nothing here changes trading, the approval book, or which process is running.
Restart the API (the dashboard is that process) after the stamp. The paper
loop does not read this value.

## Order

The desk resolves the sha in this order and stops at the first hit:

1. Environment: `GIT_SHA`, then `APP_GIT_SHA`. Older aliases `DEPLOYED_GIT_SHA`
   and `GIT_COMMIT` still work if the two above are unset.
2. A one-line file: `/app/GIT_SHA`, then `<app-root>/GIT_SHA`, then
   `<app-root>/data/DEPLOYED_SHA`.
3. `git rev-parse HEAD` in the app tree, only when `.git` exists.

The value must be a hex commit (7 to 64 characters) on its own line. A blank
file or a sentence is ignored and the next source is tried.

## Deploy step

Pick one. Do it from the host that has the checkout, against the commit that
was just put on the box.

Env line (paper and API env, then restart the API):

```bash
GIT_SHA=$(git rev-parse HEAD)
```

Or write the file into the tree the API process sees. `/app` is the container
app root. `data/DEPLOYED_SHA` sits next to the other state files when that
directory is the one mounted into the container:

```bash
git rev-parse HEAD > /app/GIT_SHA
# or, if the API reads the state mount instead of /app:
git rev-parse HEAD > data/DEPLOYED_SHA
```

Restart the API after either change. Confirm `GET /api/desk` returns
`git.source` of `env` or `file`, and `git.sha` equal to `git rev-parse HEAD`
on the host. Do not commit `GIT_SHA` or `data/DEPLOYED_SHA`.
