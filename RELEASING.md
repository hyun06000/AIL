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

1. **Bump the version** in two places (must match):
   - `reference-impl/pyproject.toml` → `version = "X.Y.Z"`
   - `reference-impl/ail/__init__.py` → `__version__ = "X.Y.Z"`

2. **Update `CHANGELOG.md`** with a new section for the version.

3. **Run the full test suite** — there should be zero failures:
   ```bash
   cd reference-impl
   python -m pytest tests/ -q
   ```

4. **Clean old build artifacts and rebuild**:
   ```bash
   rm -rf dist build *.egg-info
   python -m build
   ```
   This produces `dist/ailang-X.Y.Z.tar.gz` and
   `dist/ailang-X.Y.Z-py3-none-any.whl`.

5. **Smoke-test the wheel in a clean venv**:
   ```bash
   python -m venv /tmp/ail_verify
   source /tmp/ail_verify/bin/activate
   pip install dist/ailang-X.Y.Z-py3-none-any.whl
   ail version
   echo 'entry main(x: Text) { return "ok" }' | ail run /dev/stdin
   deactivate
   rm -rf /tmp/ail_verify
   ```

6. **(Recommended) Upload to TestPyPI first**:
   ```bash
   python -m twine upload --repository testpypi dist/*
   ```
   Then verify the install-from-TestPyPI works:
   ```bash
   python -m venv /tmp/ail_test_pypi
   source /tmp/ail_test_pypi/bin/activate
   pip install --index-url https://test.pypi.org/simple/ \
               --extra-index-url https://pypi.org/simple/ \
               ailang
   ail version
   deactivate
   ```

7. **Upload to real PyPI**:
   ```bash
   python -m twine upload dist/*
   ```

8. **Tag the release in git**:
   ```bash
   git tag -a vX.Y.Z -m "AIL vX.Y.Z"
   git push origin vX.Y.Z
   ```

9. **Verify from PyPI**:
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
