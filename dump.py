# dump.py - Generate Project Snapshot for Kairo
import os
from datetime import datetime
from pathlib import Path
import fnmatch # Used for .gitignore style pattern matching

# --- Configuration ---
# The script automatically finds all files and excludes based on the rules below.

# 1. List of directories to always exclude, regardless of .gitignore.
#    This check applies to any part of the file's path.
ALWAYS_EXCLUDE_DIRS = {
    '.git',
    '__pycache__',
    'venv',
    '.venv',
    'env',
    'ENV',
    'node_modules',
    '.vscode',
    '.idea',
    'old',
    # --- START OF CHANGE: Added WhatsApp session folders ---
    '.wwebjs_auth',
    '.wwebjs_cache',
    'WA/.wwebjs_auth',
    'WA/.wwebjs_cache',
    # --- END OF CHANGE ---
}

# 2. List of file patterns to always exclude
ALWAYS_EXCLUDE_PATTERNS = {
    '*.pyc',
    '*.pyo',
    '*.log',
    '*.db',
    '*.sqlite3',
    '.DS_Store',
    'Thumbs.db',
    'kairo_mvp_snapshot.txt', # Exclude the output file itself
    'export_user_data.py',    # Exclude the utility script
    'startup_error.log',
    'user_data.csv',          # Exclude the old CSV output
    'user_session_*.jsonl',  
    '*.tmp'
}

OUTPUT_FILENAME = "kairo_mvp_snapshot.txt"
SEPARATOR = "=" * 80
# --- End Configuration ---

def load_gitignore_patterns(root_path: Path) -> list:
    """Loads patterns from the .gitignore file in the project root."""
    gitignore_path = root_path / ".gitignore"
    patterns = []
    if not gitignore_path.is_file():
        return patterns
    
    with open(gitignore_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
    return patterns

def is_excluded(path: Path, root_path: Path, gitignore_patterns: list) -> bool:
    """
    Checks if a given path should be excluded based on our rules.
    """
    # Check against our hardcoded directory and file pattern exclusions
    if any(d in path.parts for d in ALWAYS_EXCLUDE_DIRS):
        return True
    if any(path.match(p) for p in ALWAYS_EXCLUDE_PATTERNS):
        return True

    # Check against .gitignore patterns
    relative_path_str = str(path.relative_to(root_path))
    for pattern in gitignore_patterns:
        # Handle directory patterns (e.g., 'logs/')
        if pattern.endswith('/'):
            if relative_path_str.startswith(pattern.rstrip('/')):
                return True
        # Handle file patterns
        elif fnmatch.fnmatch(relative_path_str, pattern):
            return True
            
    return False

def generate_dump():
    """
    Walks the project directory, finds all relevant files automatically,
    and generates the project dump file.
    """
    project_root = Path(__file__).parent
    gitignore_patterns = load_gitignore_patterns(project_root)
    
    files_to_include = []
    
    print("--- Scanning project files... ---")
    for path in project_root.rglob('*'): # rglob finds all files in all subdirectories
        if path.is_file() and not is_excluded(path, project_root, gitignore_patterns):
            files_to_include.append(path)

    files_to_include.sort() # Sort alphabetically for consistent output
    
    dump_content = []
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    dump_content.append(f"# Kairo Project Code Dump (v1.0 MVP)")
    dump_content.append(f"# Generated: {timestamp_str}\n\n")
    
    print("\n--- Generating snapshot ---")
    for full_path in files_to_include:
        relative_path = full_path.relative_to(project_root)
        try:
            content = full_path.read_text(encoding='utf-8', errors='replace')
            header_path = relative_path.as_posix()
            dump_content.append(SEPARATOR)
            dump_content.append(f"📄 {header_path}")
            dump_content.append(SEPARATOR)
            dump_content.append(f"\n# --- START OF FILE {header_path} ---\n")
            dump_content.append(content)
            dump_content.append(f"\n# --- END OF FILE {header_path} ---\n\n\n")
            print(f"✅ Included: {header_path}")
        except Exception as e:
            print(f"❌ Error reading {relative_path}: {e}")

    try:
        output_path = project_root / OUTPUT_FILENAME
        output_path.write_text("".join(dump_content), encoding='utf-8')
        print("-" * 30)
        print(f"✅ Dump generated successfully: {OUTPUT_FILENAME}")
        print(f"   Files included: {len(files_to_include)}")
    except Exception as e:
        print("-" * 30)
        print(f"❌ Error writing dump file {OUTPUT_FILENAME}: {e}")

if __name__ == "__main__":
    generate_dump()