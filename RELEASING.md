# Releasing AIL to PyPI

This document walks through publishing `ailang` to PyPI. After the
first publish, the same steps are used for every subsequent release
with a different version number.

## One-time setup (first release only)

1. **Create a PyPI account** if you don't have one:
   https://pypi.org/account/register/

2. **Enable 2FA** on the account (required for publishing):
   https://pypi.org/manage/account/

3. **Create an API token** scoped to "entire account" for the first
   upload. Later you can restrict it to the `ailang` project:
   https://pypi.org/manage/account/token/

   The token starts with `pypi-AgEIc...`. Save it somewhere safe.

4. **(Optional) Create a TestPyPI account** at
   https://test.pypi.org/account/register — separate from the real
   PyPI. Lets you dry-run the publish pipeline without burning real
   version numbers. Get a separate token from
   https://test.pypi.org/manage/account/token/ .

5. **Configure `~/.pypirc`** (or pass the token inline every time):

   ```ini
   [distutils]
   index-servers =
       pypi
       testpypi

   [pypi]
   username = __token__
   password = pypi-AgEIc...            # your PyPI token

   [testpypi]
   repository = https://test.pypi.org/legacy/
   username = __token__
   password = pypi-AgEIc...            # your TestPyPI token
   ```

   `chmod 600 ~/.pypirc` so other users on the machine can't read the
   token.

## Per-release checklist

> The commands below use `$VERSION` as a shell variable so you don't
> have to retype the version number in every line. Export it once
> before starting:
>
>     export VERSION=1.8.1   # or whatever you're releasing
>
> Do NOT copy a command that contains `$VERSION` into a shell that
> doesn't have the variable set — `pip install` will error with
> "No such file or directory" on the wheel path.

1. **Bump the version** in two places (must match):
   - `reference-impl/pyproject.toml` → `version = "$VERSION"`
   - `reference-impl/ail/__init__.py` → `__version__ = "$VERSION"`

2. **Update `CHANGELOG.md`** with a new section for the version.

3. **Run the full test suite** — there should be zero failures:
   ```bash
   cd reference-impl
   python -m pytest tests/ -q
   ```

4. **Refresh the bundled language reference card.** The wheel ships a
   copy of the spec at `ail/reference_card.md` so `ail ask` has the
   full reference available on pip installs. The single source of
   truth is `spec/08-reference-card.ai.md`; the bundled copy is a
   release artifact that must be refreshed before every build:
   ```bash
   cp spec/08-reference-card.ai.md reference-impl/ail/reference_card.md
   ```
   `tests/test_spec_bundled.py` fails if the two files have drifted,
   so running `pytest` above also verifies this is in sync.

5. **Clean old build artifacts and rebuild**:
   ```bash
   cd reference-impl
   rm -rf dist build *.egg-info
   python -m build
   ```
   This produces `dist/ailang-$VERSION.tar.gz` and
   `dist/ailang-$VERSION-py3-none-any.whl`. Verify the wheel contains
   `ail/reference_card.md` and does NOT contain a stray `ail_mvp/`
   directory (a leftover from the v1.8 package rename):
   ```bash
   python -m zipfile -l dist/ailang-$VERSION-py3-none-any.whl \
       | grep -E 'reference_card|ail_mvp'
   # expected: one line with ail/reference_card.md, and no ail_mvp.
   ```

6. **Smoke-test the wheel in a clean venv**:
   ```bash
   python -m venv /tmp/ail_verify
   /tmp/ail_verify/bin/pip install dist/ailang-$VERSION-py3-none-any.whl
   /tmp/ail_verify/bin/ail version
   echo 'entry main(x: Text) { return "ok" }' > /tmp/test.ail
   /tmp/ail_verify/bin/ail run /tmp/test.ail --mock
   # Also verify the reference card loads (not the degraded fallback):
   /tmp/ail_verify/bin/python -c "from ail.authoring import _load_reference_card; c = _load_reference_card(); assert len(c) > 5000, f'fallback leaked: {len(c)} chars'"
   rm -rf /tmp/ail_verify /tmp/test.ail
   ```
   The `--mock` flag is important — a clean venv has no Ollama or
   Anthropic credentials, so an intent call would fail without it.
   The reference-card check guards against the spec file being
   silently absent from the wheel.

7. **(Recommended) Upload to TestPyPI first** — but note TestPyPI
   does not allow re-uploading a version number that already exists
   (same rule as real PyPI). If you burned this version on TestPyPI
   during an earlier dry run, bump the patch number before trying
   again, or skip this step. Check what's already uploaded with:
   ```bash
   curl -s https://test.pypi.org/pypi/ailang/json \
       | python -c "import sys,json; print(list(json.load(sys.stdin)['releases'].keys()))"
   ```
   ```bash
   python -m twine upload --repository testpypi dist/*
   ```
   Then verify the install-from-TestPyPI works:
   ```bash
   python -m venv /tmp/ail_test_pypi
   /tmp/ail_test_pypi/bin/pip install \
       --index-url https://test.pypi.org/simple/ \
       --extra-index-url https://pypi.org/simple/ \
       ailang
   /tmp/ail_test_pypi/bin/ail version
   rm -rf /tmp/ail_test_pypi
   ```

8. **Upload to real PyPI**:
   ```bash
   python -m twine upload dist/*
   ```
   This is irreversible — PyPI does not allow re-uploading the same
   version under any circumstances. If the upload fails halfway, the
   fix is to bump to the next patch version and try again.

9. **Tag the release in git**:
   ```bash
   git tag -a v$VERSION -m "AIL v$VERSION"
   git push origin v$VERSION
   ```

10. **Verify from PyPI**:
   ```bash
   pip install --upgrade ailang
   ail version
   ```

## Dependency notes

Runtime dependencies: **none**. AIL runs on the Python stdlib alone
(urllib for the http effect, json for calibration persistence,
concurrent.futures for parallelism, threading for trace locking).

Optional dependencies, installed only when the user asks for them:
- `anthropic>=0.34` (via `pip install 'ailang[anthropic]'`) —
  needed for the Anthropic adapter. Ollama and Mock adapters have no
  extra requirements.

Build-time dependencies: `build`, `twine`. Install once on the
publisher's machine:
```bash
pip install build twine
```

## Security reminders

- Never commit `~/.pypirc` or tokens to git.
- Tokens are one-way: if leaked, revoke and regenerate at
  https://pypi.org/manage/account/token/ .
- 2FA is mandatory for PyPI publishing since 2024.
- If you want Claude (the AI) to run any of this on your behalf, share
  the token via a secure channel and revoke it after use.
