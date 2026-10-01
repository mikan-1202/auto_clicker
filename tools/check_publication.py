"""公開前に全Git参照の到達可能オブジェクトを検査する（値は出力しない）。"""

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

PUBLIC_EMAIL = b"mikan-1202@users.noreply.github.com"
PERSONAL_PATH = re.compile(rb"(?i)[a-z]:[\\/]+Users[\\/]+")
CREDENTIAL = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    rb"|(?:AKIA|ASIA)[A-Z0-9]{16}"
    rb"|gh[pousr]_[A-Za-z0-9]{30,}"
    rb"|sk-[A-Za-z0-9_-]{30,}"
    rb"|(?i:api[_-]?key|password|secret|access[_-]?token)"
    rb"\s*[:=]\s*[\x22\x27][^\x22\x27\r\n]{8,}[\x22\x27]"
)


def git(*args):
    return subprocess.check_output(["git", *args])


def sensitive_filename(path):
    name = PurePosixPath(path).name.lower()
    return (
        name == ".env"
        or (name.startswith(".env.") and name not in (".env.example", ".env.sample"))
        or name in ("credentials.json", "secrets.json")
        or (name.startswith("credentials.") and name.endswith(".json"))
        or name.endswith((".pem", ".key", ".pyc", ".pyo"))
        or "__pycache__" in PurePosixPath(path).parts
    )


def main():
    failures = []
    root = Path(git("rev-parse", "--show-toplevel").decode().strip())
    objects = {}
    for line in git("rev-list", "--objects", "--all").splitlines():
        object_id, _, path = line.partition(b" ")
        objects[object_id.decode()] = path.decode("utf-8", errors="replace")
        if sensitive_filename(objects[object_id.decode()]):
            failures.append(("sensitive-filename", objects[object_id.decode()]))
    counts = {}
    for object_id, path in objects.items():
        kind = git("cat-file", "-t", object_id).strip().decode()
        counts[kind] = counts.get(kind, 0) + 1
        if kind not in ("blob", "commit", "tag"):
            continue
        data = git("cat-file", kind, object_id)
        if kind in ("commit", "tag"):
            for email in re.findall(rb"(?m)^(?:author|committer|tagger) .*? <([^>]+)>", data):
                if email != PUBLIC_EMAIL:
                    failures.append(("identity", object_id[:12]))
        if PERSONAL_PATH.search(data):
            failures.append(("personal-path", path or object_id[:12]))
        if CREDENTIAL.search(data):
            failures.append(("credential-pattern", path or object_id[:12]))
    # Include pending edits and new, non-ignored files before committing.
    paths = git("ls-files", "--full-name", "--cached", "--others", "--exclude-standard", "-z")
    for name in set(paths.split(b"\0")) - {b""}:
        path = name.decode("utf-8")
        file = root / path
        if not file.is_file():
            continue
        if sensitive_filename(path):
            failures.append(("working-tree-sensitive-filename", path))
        data = file.read_bytes()
        if PERSONAL_PATH.search(data):
            failures.append(("working-tree-personal-path", path))
        if CREDENTIAL.search(data):
            failures.append(("working-tree-credential-pattern", path))
    print("Reachable objects:", counts)
    for category, location in sorted(set(failures)):
        print(f"FAIL {category}: {location}")
    if failures:
        return 1
    print("PASS: no non-public commit email, user path, bytecode or credential-pattern match")
    print("Pattern scanning is not a complete security or license audit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
