"""
OTA (Over-The-Air) update utilities for RokCommon

Features:
- File upload and management
- Backup system for current files
- GitHub repository sync
- Safe file operations with rollback capability

Generic implementation - works with any project via overlay deployment
"""

import os
import gc
import machine
import ujson as json

try:
    import urequests as requests
except ImportError:
    import requests

# Configuration for GitHub sync
DEFAULT_GITHUB_REPO = "FirstNight1/Rokenbok-Wifi-Esp32"
DEFAULT_GITHUB_BRANCH = "main"

# Files to ignore during updates (preserve local configs)
IGNORE_FILES = [
    "variables/config.json",  # Preserve local configuration
    "ota_backup.json",  # Preserve backup metadata
    "boot.py.bak",  # Preserve backup files
    ".DS_Store",  # System files
    "__pycache__",  # Python cache
]


# ---------------------------------------------------------
# Backup and restore functionality
# ---------------------------------------------------------
def backup_system():
    """Create a backup of critical system files before OTA update"""
    backup_meta = {"timestamp": None, "files": []}

    try:
        # Get current timestamp (simple counter since we don't have RTC)
        try:
            with open("ota_backup.json", "r") as f:
                old_meta = json.load(f)
                backup_meta["timestamp"] = old_meta.get("timestamp", 0) + 1
        except:
            backup_meta["timestamp"] = 1

        print("Creating system backup...")

        # Backup critical files
        critical_files = [
            "main.py",
            "boot.py",
        ]

        for file_path in critical_files:
            if file_exists(file_path):
                backup_file = f"{file_path}.bak"
                copy_file(file_path, backup_file)
                backup_meta["files"].append(
                    {"original": file_path, "backup": backup_file}
                )
                print(f"Backed up: {file_path}")

        # Save backup metadata
        with open("ota_backup.json", "w") as f:
            json.dump(backup_meta, f)

        print(f"Backup completed. {len(backup_meta['files'])} files backed up.")
        return True, backup_meta

    except Exception as e:
        print(f"Backup failed: {e}")
        return False, str(e)


def restore_backup():
    """Restore system from backup files"""
    try:
        with open("ota_backup.json", "r") as f:
            backup_meta = json.load(f)

        print("Restoring from backup...")

        for file_info in backup_meta["files"]:
            original = file_info["original"]
            backup = file_info["backup"]

            if file_exists(backup):
                copy_file(backup, original)
                print(f"Restored: {original}")
            else:
                print(f"Warning: Backup file not found: {backup}")

        print("Backup restore completed.")
        return True

    except Exception as e:
        print(f"Restore failed: {e}")
        return False


# ---------------------------------------------------------
# File system utilities
# ---------------------------------------------------------
def file_exists(path):
    """Check if file exists"""
    try:
        os.stat(path)
        return True
    except:
        return False


def copy_file(src, dst):
    """Copy a file from src to dst"""
    # Create directory if it doesn't exist
    dst_dir = "/".join(dst.split("/")[:-1])
    if dst_dir:
        make_dirs(dst_dir)

    # Copy file content
    with open(src, "rb") as f_src:
        with open(dst, "wb") as f_dst:
            while True:
                chunk = f_src.read(1024)
                if not chunk:
                    break
                f_dst.write(chunk)


def make_dirs(path):
    """Create directory path recursively"""
    if not path or path == "/":
        return

    try:
        os.stat(path)
        return  # Directory exists
    except:
        pass  # Directory doesn't exist

    # Create parent directories first
    parent = "/".join(path.split("/")[:-1])
    if parent:
        make_dirs(parent)

    try:
        os.mkdir(path)
    except:
        pass  # Directory might already exist


def delete_file(path):
    """Safely delete a file"""
    try:
        os.remove(path)
        return True
    except:
        return False


def list_files_recursive(root_dir=".", ignore_patterns=None):
    """List all files recursively from root_dir"""
    if ignore_patterns is None:
        ignore_patterns = IGNORE_FILES

    files = []

    def should_ignore(path):
        for pattern in ignore_patterns:
            if pattern in path:
                return True
        return False

    def scan_directory(dir_path, relative_path=""):
        try:
            entries = os.listdir(dir_path)
            for entry in entries:
                full_path = f"{dir_path}/{entry}" if dir_path != "." else entry
                rel_path = f"{relative_path}/{entry}" if relative_path else entry

                if should_ignore(rel_path):
                    continue

                try:
                    # Check if it's a directory
                    try:
                        os.listdir(full_path)  # If this works, it's a directory
                        scan_directory(full_path, rel_path)
                    except:
                        # It's a file
                        files.append(rel_path)
                except:
                    # Assume it's a file if stat fails
                    files.append(rel_path)

        except Exception as e:
            print(f"Error scanning directory {dir_path}: {e}")

    scan_directory(root_dir)
    return files


def get_file_info(path):
    """Get file information (size, etc.)"""
    try:
        stat_result = os.stat(path)
        # MicroPython stat returns a tuple
        size = stat_result[6] if len(stat_result) > 6 else 0
        return {"path": path, "size": size, "exists": True}
    except:
        return {"path": path, "size": 0, "exists": False}


# ---------------------------------------------------------
# File upload functionality
# ---------------------------------------------------------
def save_uploaded_file(filename, content):
    """Save uploaded file content to filesystem"""
    try:
        # Sanitize filename - prevent directory traversal
        filename = filename.replace("../", "").replace("..\\", "")
        filename = filename.strip("/\\")

        # Create directory if needed
        dir_path = "/".join(filename.split("/")[:-1])
        if dir_path:
            make_dirs(dir_path)

        # Save file
        if isinstance(content, str):
            with open(filename, "w") as f:
                f.write(content)
        else:
            with open(filename, "wb") as f:
                f.write(content)

        print(f"File saved: {filename}")
        return True, f"File '{filename}' saved successfully"

    except Exception as e:
        error_msg = f"Failed to save file '{filename}': {e}"
        print(error_msg)
        return False, error_msg


# ---------------------------------------------------------
# GitHub integration
# ---------------------------------------------------------
def download_github_file(repo, branch, file_path):
    """Download a single file from GitHub repository"""
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{file_path}"

    try:
        print(f"Downloading: {url}")
        response = requests.get(url)

        if response.status_code == 200:
            return True, response.text
        else:
            return False, f"HTTP {response.status_code}"

    except Exception as e:
        return False, str(e)
    finally:
        if "response" in locals():
            response.close()
        gc.collect()


def get_github_file_list(repo, branch, folder=""):
    """Get list of files from GitHub repository using GitHub API"""
    api_url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"

    try:
        print(f"Fetching file list from: {api_url}")
        response = requests.get(api_url)

        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"

        data = json.loads(response.text)
        files = []

        for item in data.get("tree", []):
            if item["type"] == "blob":  # It's a file
                file_path = item["path"]

                # Filter by folder if specified
                if folder:
                    if file_path.startswith(f"{folder}/"):
                        # Remove folder prefix
                        local_path = file_path[len(f"{folder}/") :]
                        files.append(
                            {
                                "path": local_path,
                                "github_path": file_path,
                                "size": item.get("size", 0),
                            }
                        )
                else:
                    files.append(
                        {
                            "path": file_path,
                            "github_path": file_path,
                            "size": item.get("size", 0),
                        }
                    )

        return True, files

    except Exception as e:
        return False, str(e)
    finally:
        if "response" in locals():
            response.close()
        gc.collect()


def sync_from_github(repo=None, branch=None, folder=None, dry_run=False):
    """Sync from GitHub repository"""
    if not repo:
        repo = DEFAULT_GITHUB_REPO
    if not branch:
        branch = DEFAULT_GITHUB_BRANCH

    results = {"downloaded": [], "failed": [], "skipped": []}

    try:
        print(f"Starting GitHub sync from {repo}/{branch}/{folder or 'root'}")

        # Get file list from GitHub
        success, github_files = get_github_file_list(repo, branch, folder)
        if not success:
            return False, f"Failed to get GitHub file list: {github_files}"

        print(f"Found {len(github_files)} files on GitHub")

        if dry_run:
            return True, {"dry_run": True, "would_download": github_files}

        # Create backup before sync
        backup_success, backup_info = backup_system()
        if not backup_success:
            print(f"Backup warning: {backup_info}")

        # Download each file
        for file_info in github_files:
            local_path = file_info["path"]
            github_path = file_info["github_path"]

            # Skip ignored files
            if any(pattern in local_path for pattern in IGNORE_FILES):
                results["skipped"].append(local_path)
                continue

            # Download file
            success, content = download_github_file(repo, branch, github_path)
            if success:
                save_success, save_msg = save_uploaded_file(local_path, content)
                if save_success:
                    results["downloaded"].append(local_path)
                    print(f"✓ Downloaded: {local_path}")
                else:
                    results["failed"].append(f"{local_path}: {save_msg}")
            else:
                results["failed"].append(f"{local_path}: {content}")

            # Free memory frequently
            gc.collect()

        print(f"GitHub sync completed:")
        print(f"  Downloaded: {len(results['downloaded'])}")
        print(f"  Failed: {len(results['failed'])}")
        print(f"  Skipped: {len(results['skipped'])}")

        return True, results

    except Exception as e:
        error_msg = f"GitHub sync failed: {e}"
        print(error_msg)
        return False, error_msg


# ---------------------------------------------------------
# System utilities
# ---------------------------------------------------------
def restart_system():
    """Restart the ESP32 system"""
    try:
        print("Restarting system...")
        machine.reset()
    except:
        print("Reset failed, attempting soft reboot...")
        import sys

        sys.exit()


def clean_memory():
    """Clean up memory and run garbage collection"""
    gc.collect()
    try:
        print(f"Free memory: {gc.mem_free()} bytes")
    except:
        pass


def format_file_size(size_bytes):
    """Format file size in human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024} KB"
    else:
        return f"{size_bytes // (1024 * 1024)} MB"


def validate_github_url(url):
    """Validate and parse GitHub repository URL"""
    try:
        url = url.strip()
        if not url.startswith("https://github.com/"):
            return False, "URL must start with https://github.com/"

        # Remove GitHub domain
        path = url[19:]  # Remove "https://github.com/"

        parts = path.split("/")
        if len(parts) < 2:
            return False, "Invalid repository URL format"

        owner = parts[0]
        repo = parts[1]
        repo_name = f"{owner}/{repo}"

        branch = "main"
        folder = ""

        # Check for branch and folder specification
        if len(parts) > 2:
            if parts[2] == "tree" and len(parts) > 3:
                branch = parts[3]
                if len(parts) > 4:
                    folder = "/".join(parts[4:])

        return True, (repo_name, branch, folder)

    except Exception as e:
        return False, str(e)
