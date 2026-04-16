from pathlib import Path

OUTPUT_FILE = "structure.txt"

# folders/files to ignore
IGNORE_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build"}
IGNORE_FILES = {"structure.txt"}

def should_skip(path: Path):
    return (
        any(part in IGNORE_DIRS for part in path.parts)
        or path.name in IGNORE_FILES
    )

def append_file(path: Path):
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"Skipping {path}: {e}")
        return

    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"FILE: {path}\n")
        f.write("=" * 80 + "\n\n")
        f.write(content + "\n")

    print(f"Added: {path}")

def scan_directory(root="."):
    root_path = Path(root)

    for path in root_path.rglob("*"):
        if path.is_file() and not should_skip(path):
            append_file(path)

if __name__ == "__main__":
    # reset file each run (optional but recommended)
    open(OUTPUT_FILE, "w", encoding="utf-8").close()

    scan_directory(".")
    print("\nDone. structure.txt generated.")
