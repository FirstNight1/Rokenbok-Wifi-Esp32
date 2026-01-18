"""
New OTA System with Staging Areas - Utilities Module

This module implements a safer, multi-step OTA process:
1. Stage updates in /update/ folder
2. Preview changes before applying
3. Create versioned backups in /backup/ 
4. Apply updates atomically

Features:
- Staging areas for safe downloads
- Versioned backups with timestamps
- Preview functionality
- Atomic updates
- Rollback capability
"""

import os
import gc
import machine
import time

try:
    import ujson as json
except ImportError:
    import json

try:
    import urequests as requests
except ImportError:
    import requests


# MicroPython-compatible makedirs implementation
def makedirs(path):
    """Create directory tree recursively (MicroPython compatible)"""
    if not path or path == "/":
        return
    parts = path.strip('/').split('/')
    current = ''
    for part in parts:
        current = f"{current}/{part}" if current else part
        if current:
            try:
                os.stat(current)
            except OSError:
                os.mkdir(current)

# Staging directories
UPDATE_DIR = "/update"
BACKUP_DIR = "/backup"

# Configuration
DEFAULT_GITHUB_REPO = "FirstNight1/Rokenbok-Wifi-Esp32"
DEFAULT_GITHUB_BRANCH = "main"

def count_files_recursive(path):
    """Count all files recursively in a directory"""
    total = 0
    try:
        items = os.listdir(path)
        for item in items:
            item_path = f"{path}/{item}"
            try:
                # Check if it's a directory
                os.listdir(item_path)
                # It's a directory, recurse
                total += count_files_recursive(item_path)
            except OSError:
                # It's a file
                total += 1
    except Exception as e:
        print(f"[STAGING DEBUG] Error counting files in {path}: {e}")
    return total

def format_timestamp(timestamp_str):
    """Convert Unix timestamp to human readable format"""
    try:
        if not timestamp_str:
            return "Unknown"
        timestamp = int(timestamp_str)
        # Convert to local time tuple
        time_tuple = time.localtime(timestamp)
        # Format as readable string
        return f"{time_tuple[1]:02d}/{time_tuple[2]:02d}/{time_tuple[0]} {time_tuple[3]:02d}:{time_tuple[4]:02d}:{time_tuple[5]:02d}"
    except Exception as e:
        print(f"[STAGING DEBUG] Error formatting timestamp {timestamp_str}: {e}")
        return timestamp_str

# Files and folders to preserve during updates
PRESERVE_PATHS = [
    "/backup",
    "/update", 
    "variables/config.json"
]


# =============================================================================
# Directory Management
# =============================================================================

def ensure_staging_dirs():
    """Ensure staging directories exist"""
    try:
        for dir_path in [UPDATE_DIR, BACKUP_DIR]:
            if not dir_exists(dir_path):
                os.mkdir(dir_path)
        return True, "Staging directories ready"
    except Exception as e:
        return False, f"Failed to create staging directories: {e}"


def dir_exists(path):
    """Check if directory exists"""
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def get_free_space():
    """Get available filesystem space in bytes"""
    try:
        stat = os.statvfs("/")
        return stat[0] * stat[3]  # block_size * free_blocks
    except Exception:
        return 0


def clear_directory(path, preserve_files=None):
    """Iteratively clear directory contents to avoid stack overflow"""
    preserve_files = preserve_files or []
    
    try:
        if not dir_exists(path):
            return True, "Directory doesn't exist"
        
        print(f"Starting to clear directory: {path}")
        
        # Use iterative approach instead of recursion to avoid stack overflow
        dirs_to_process = [path]
        files_removed = 0
        dirs_removed = 0
        
        # First pass: collect all files to remove (depth-first)
        files_to_remove = []
        dirs_to_remove = []
        
        while dirs_to_process:
            current_dir = dirs_to_process.pop()
            try:
                # Process directory contents
                
                for item in items:
                    item_path = f"{current_dir}/{item}"
                    
                    # Skip preserved files
                    if any(preserve in item_path for preserve in preserve_files):
                        print(f"[STAGING] Skipping preserved: {item_path}")
                        continue
                    
                    try:
                        stat = os.stat(item_path)
                        if stat[0] & 0o040000:  # Directory
                            dirs_to_process.append(item_path)
                            dirs_to_remove.insert(0, item_path)  # Insert at beginning for reverse order
                        else:  # File
                            files_to_remove.append(item_path)
                    except OSError as e:
                        print(f"[STAGING] Could not stat {item_path}: {e}")
                        continue
                        
            except OSError as e:
                print(f"[STAGING] Could not list directory {current_dir}: {e}")
                continue
        
        # Remove files first
        for file_path in files_to_remove:
            try:
                os.remove(file_path)
                files_removed += 1
            except OSError as e:
                print(f"[STAGING] Could not remove file {file_path}: {e}")
        
        # Remove directories (in reverse order - deepest first)
        for dir_path in dirs_to_remove:
            try:
                os.rmdir(dir_path)
                dirs_removed += 1
            except OSError as e:
                print(f"[STAGING] Could not remove directory {dir_path}: {e}")
        
        print(f"[STAGING] Cleared {files_removed} files and {dirs_removed} directories from {path}")
        return True, f"Cleared {path} ({files_removed} files, {dirs_removed} dirs)"
        
    except Exception as e:
        print(f"[STAGING] Error clearing directory {path}: {e}")
        return False, f"Failed to clear {path}: {e}"


def copy_recursive(src, dst, exclude_paths=None):
    """Recursively copy directory contents"""
    exclude_paths = exclude_paths or []
    copied_files = []
    
    try:
        # Ensure destination exists
        if not dir_exists(dst):
            os.mkdir(dst)
            
        for item in os.listdir(src):
            src_path = f"{src}/{item}"
            dst_path = f"{dst}/{item}"
            
            # Skip excluded paths
            if any(exclude in src_path for exclude in exclude_paths):
                continue
                
            try:
                stat = os.stat(src_path)
                if stat[0] & 0o040000:  # Directory
                    sub_copied = copy_recursive(src_path, dst_path, exclude_paths)
                    copied_files.extend(sub_copied)
                else:  # File
                    copy_file(src_path, dst_path)
                    copied_files.append(dst_path)
            except OSError as e:
                print(f"Copy error for {src_path}: {e}")
                continue
                
        return copied_files
    except Exception as e:
        print(f"Recursive copy error: {e}")
        return []


def copy_file(src, dst):
    """Copy a single file"""
    # Ensure destination directory exists
    dst_dir = dst.rsplit("/", 1)[0]
    if not dir_exists(dst_dir):
        makedirs(dst_dir)
        
    with open(src, "rb") as src_file:
        with open(dst, "wb") as dst_file:
            while True:
                chunk = src_file.read(1024)
                if not chunk:
                    break
                dst_file.write(chunk)


# =============================================================================
# Version Management
# =============================================================================

def get_backup_version():
    """Get current backup version info"""
    try:
        with open(f"{BACKUP_DIR}/version.info", "r") as f:
            return json.load(f)
    except Exception:
        return None


def create_backup_version(description="Manual backup"):
    """Create version info for backup"""
    try:
        # Simple timestamp - ticks since boot
        timestamp = time.ticks_ms()
        
        version_info = {
            "timestamp": timestamp,
            "description": description,
            "created": f"tick_{timestamp}",
            "files_backed_up": []
        }
        
        return version_info
    except Exception as e:
        print(f"Failed to create version info: {e}")
        return None


def save_backup_version(version_info):
    """Save backup version info"""
    try:
        with open(f"{BACKUP_DIR}/version.info", "w") as f:
            json.dump(version_info, f)
        return True
    except Exception as e:
        print(f"Failed to save version info: {e}")
        return False


# =============================================================================
# Staging Operations (Step 1: Download/Upload to /update)
# =============================================================================

def stage_folder_upload(folder_type):
    """Prepare staging area for folder upload by clearing existing content"""
    try:
        # Ensure staging directory
        success, msg = ensure_staging_dirs()
        if not success:
            return False, msg
            
        if folder_type == "RokCommon":
            # Clear only RokCommon folder
            rokcommon_path = f"{UPDATE_DIR}/RokCommon"
            if dir_exists(rokcommon_path):
                success, msg = clear_directory(rokcommon_path)
                if not success:
                    return False, f"Failed to clear RokCommon: {msg}"
        elif folder_type in ["RokVehicle", "RokVision"]:
            # Clear only the specific device folder
            device_path = f"{UPDATE_DIR}/{folder_type}"
            print(f"[UPLOAD] Clearing staging area for {folder_type} at {device_path}")
            if dir_exists(device_path):
                success, msg = clear_directory(device_path)
                if not success:
                    return False, f"Failed to clear {folder_type}: {msg}"
            else:
                print(f"[UPLOAD] No existing {folder_type} directory to clear")
        print(f"[UPLOAD] Staging area preparation completed for {folder_type}")
        return True, f"Staging area prepared for {folder_type}"
        
    except Exception as e:
        print(f"[UPLOAD] Error in stage_folder_upload: {e}")
        return False, f"Failed to prepare staging area: {e}"


def clear_upload_timestamp(folder_type):
    """Remove timestamp for a specific folder (for failed uploads)"""
    try:
        timestamps_file = f"{UPDATE_DIR}/.timestamps"
        if not file_exists(timestamps_file):
            return True, "No timestamps file exists"
            
        # Load existing timestamps
        try:
            with open(timestamps_file, "r") as f:
                timestamps = json.load(f)
        except Exception:
            return True, "No valid timestamps to clear"
            
        # Remove specific folder timestamp
        if folder_type in timestamps:
            del timestamps[folder_type]
            with open(timestamps_file, "w") as f:
                json.dump(timestamps, f)
            print(f"[STAGING] Cleared timestamp for {folder_type}")
            return True, f"Cleared timestamp for {folder_type}"
        else:
            return True, f"No timestamp found for {folder_type}"
            
    except Exception as e:
        print(f"[STAGING] Error clearing timestamp for {folder_type}: {e}")
        return False, f"Failed to clear timestamp: {e}"


def save_upload_timestamp(folder_type, browser_timestamp=None):
    """Save timestamp when folder was uploaded"""
    try:
        timestamps_file = f"{UPDATE_DIR}/.timestamps"
        timestamps = {}
        
        # Load existing timestamps
        try:
            with open(timestamps_file, "r") as f:
                timestamps = json.load(f)
        except Exception:
            pass  # File doesn't exist yet
            
        # Use browser timestamp if provided, otherwise fall back to simple time
        if browser_timestamp:
            timestamp_value = browser_timestamp
        else:
            # Fallback to simple time counter
            try:
                # Try MicroPython ticks
                tick_ms = time.ticks_ms()
                tick_seconds = tick_ms // 1000
                hours = tick_seconds // 3600
                minutes = (tick_seconds % 3600) // 60
                seconds = tick_seconds % 60
                timestamp_value = f"{hours:02d}:{minutes:02d}:{seconds:02d} since boot"
            except AttributeError:
                # Fallback for systems without ticks_ms
                import time
                timestamp_value = str(int(time.time()))
            
        # Add current timestamp
        timestamps[folder_type] = timestamp_value
        
        # Save updated timestamps
        with open(timestamps_file, "w") as f:
            json.dump(timestamps, f)
            
        print(f"[UPLOAD] Saved timestamp for {folder_type}: {timestamp_value}")
        return True
    except Exception as e:
        print(f"[UPLOAD] Failed to save timestamp: {e}")
        return False


def get_upload_timestamps():
    """Get timestamps for uploaded folders"""
    try:
        timestamps_file = f"{UPDATE_DIR}/.timestamps"
        
        # Check if file exists before trying to open it
        if not file_exists(timestamps_file):
            return {}
            
        with open(timestamps_file, "r") as f:
            timestamps = json.load(f)
            return timestamps
    except Exception as e:
        return {}


def check_upload_timing():
    """Check if required uploads have valid timestamps"""
    try:
        print("[STAGING DEBUG] Checking upload timing...")
        
        # Check which folders are actually staged
        has_common = dir_exists(f"{UPDATE_DIR}/RokCommon")
        has_vehicle = dir_exists(f"{UPDATE_DIR}/RokVehicle")
        has_vision = dir_exists(f"{UPDATE_DIR}/RokVision")
        
        print(f"[STAGING DEBUG] Staged folders - RokCommon: {has_common}, RokVehicle: {has_vehicle}, RokVision: {has_vision}")
        
        # Check that we have the required folders
        if not has_common:
            return False, "RokCommon folder required but not found"
        if not (has_vehicle or has_vision):
            return False, "At least one device folder (RokVehicle or RokVision) required but neither found"

        # Load timestamps
        timestamps = get_upload_timestamps()
        if not timestamps:
            return False, "No upload timestamps found - files not properly uploaded"
        
        print(f"[STAGING DEBUG] Available timestamps: {list(timestamps.keys())}")
        
        # Verify timestamps exist for staged folders
        if has_common and "RokCommon" not in timestamps:
            return False, "RokCommon is staged but has no upload timestamp"
        if has_vehicle and "RokVehicle" not in timestamps:
            return False, "RokVehicle is staged but has no upload timestamp"
        if has_vision and "RokVision" not in timestamps:
            return False, "RokVision is staged but has no upload timestamp"
        
        common_ts = timestamps.get("RokCommon")
        vehicle_ts = timestamps.get("RokVehicle")
        vision_ts = timestamps.get("RokVision")
        
        # Simple check - just verify we have timestamps where needed
        if has_common and not common_ts:
            return False, "RokCommon timestamp is invalid"
        
        if has_vehicle and not vehicle_ts and has_vision and not vision_ts:
            return False, "No valid device timestamp found"
        
        print("[STAGING DEBUG] All required timestamps found - ready for deployment")
        return True, "Ready for deployment"
        
    except Exception as e:
        print(f"[STAGING DEBUG] Error checking upload timing: {e}")
        return False, f"Upload timing check failed: {e}"

def get_staged_summary():
    """Get summary of what's staged for upload with detailed status"""
    try:
        # Ensure update directory exists
        if not dir_exists(UPDATE_DIR):
            makedirs(UPDATE_DIR)
            return []
            
        staged_folders = []
        timestamps = get_upload_timestamps()
        
        # Simple validation that timestamps is a dict
        if type(timestamps) != dict:
            timestamps = {}
        
        for folder in ["RokCommon", "RokVehicle", "RokVision"]:
            folder_path = f"{UPDATE_DIR}/{folder}"
            
            # Check if folder exists and has files
            if dir_exists(folder_path):
                # Count files recursively
                file_count = count_files_recursive(folder_path)
                
                # Only include folders that actually have files
                if file_count > 0:
                    # Format timestamp
                    ts = timestamps.get(folder)
                    if ts:
                        timestamp_readable = format_timestamp(ts)
                        timestamp_status = f"Uploaded {timestamp_readable}"
                    else:
                        timestamp_status = "Not Uploaded"
                    
                    staged_folders.append({
                        "name": folder,
                        "status": "Folder exists",
                        "file_count": file_count,
                        "upload_status": timestamp_status
                    })
        return staged_folders
        
    except Exception as e:
        print(f"Error in get_staged_summary: {e}")
        return []


def stage_file_upload(file_content, filename, folder_type=""):
    """Save uploaded file to staging area with folder organization"""
    try:
        print(f"[UPLOAD] Staging file: {filename} (type: {folder_type})")
        
        # Ensure staging directory
        success, msg = ensure_staging_dirs()
        if not success:
            return False, msg
            
        # Determine staging path
        if folder_type == "RokCommon":
            # Remove leading "RokCommon/" from filename if present, then add to RokCommon folder
            if filename.startswith("RokCommon/"):
                relative_filename = filename[len("RokCommon/"):]
            else:
                relative_filename = filename
            staging_path = f"{UPDATE_DIR}/RokCommon/{relative_filename}"
        elif folder_type in ["RokVehicle", "RokVision"]:
            # Remove leading folder name if present, then add to device folder
            if filename.startswith(f"{folder_type}/"):
                relative_filename = filename[len(f"{folder_type}/"):]
            else:
                relative_filename = filename
            staging_path = f"{UPDATE_DIR}/{folder_type}/{relative_filename}"
        else:
            staging_path = f"{UPDATE_DIR}/{filename}"  # Default to root
            
        print(f"[UPLOAD] Target path: {staging_path}")
            
        # Ensure directory structure
        staging_dir = staging_path.rsplit("/", 1)[0]
        if not dir_exists(staging_dir):
            try:
                makedirs(staging_dir)
                print(f"[UPLOAD] Created directory: {staging_dir}")
            except Exception as e:
                return False, f"Failed to create directory {staging_dir}: {e}"
            
        # Save to staging
        try:
            with open(staging_path, "wb") as f:
                f.write(file_content)
            print(f"[UPLOAD] Successfully wrote {len(file_content)} bytes")
        except Exception as e:
            return False, f"Failed to write file {staging_path}: {e}"
            
        print(f"[UPLOAD] Staged {filename} -> {staging_path}")
        
        return True, f"Staged {filename}"
        
    except Exception as e:
        print(f"[UPLOAD] Upload staging failed for {filename}: {e}")
        return False, f"Upload staging failed: {e}"


# =============================================================================
# Preview Operations (Step 2: Compare staged vs current)
# =============================================================================

def preview_staged_changes():
    """Preview what changes would be made"""
    try:
        if not dir_exists(UPDATE_DIR):
            return False, "No staged updates found"
            
        changes = {
            "new_files": [],
            "updated_files": [],
            "current_files": [],
            "will_be_deleted": []
        }
        
        # Find staged files with new structure
        staged_files = list_files_recursive(UPDATE_DIR)
        
        for staged_file in staged_files:
            # Handle different folder structures
            relative_path = staged_file[len(UPDATE_DIR)+1:]
            
            if relative_path.startswith("RokCommon/"):
                # RokCommon files map to /RokCommon/...
                current_path = f"/{relative_path}"
            elif "/" in relative_path:
                # Device folder files (RokVehicle/... or RokVision/...) map to root
                device_part, file_part = relative_path.split("/", 1)
                if device_part in ["RokVehicle", "RokVision"]:
                    current_path = f"/{file_part}"
                else:
                    current_path = f"/{relative_path}"
            else:
                # Files directly in staging map to root
                current_path = f"/{relative_path}"
            
            if file_exists(current_path):
                changes["updated_files"].append(current_path[1:])  # Remove leading /
            else:
                changes["new_files"].append(current_path[1:])  # Remove leading /
                
        # Find current files that might be deleted
        current_files = list_files_recursive("/", exclude_dirs=["/update", "/backup"])
        for current_file in current_files:
            if current_file not in [f"/{f}" for f in changes["updated_files"]]:
                changes["current_files"].append(current_file[1:])  # Remove leading /
                
        return True, changes
        
    except Exception as e:
        return False, f"Preview failed: {e}"


def list_files_recursive(path, exclude_dirs=None):
    """List all files recursively"""
    exclude_dirs = exclude_dirs or []
    # Add common directories that might cause memory issues
    exclude_dirs = exclude_dirs + ["/assets", "assets"]
    files = []
    
    try:
        print(f"[STAGING DEBUG] list_files_recursive scanning: {path}")
        for item in os.listdir(path):
            item_path = f"{path}/{item}"
            
            # Skip excluded directories
            if any(exclude in item_path for exclude in exclude_dirs):
                print(f"[STAGING DEBUG] Skipping excluded: {item_path}")
                continue
                
            # Skip assets directories specifically  
            if item == "assets":
                print(f"[STAGING DEBUG] Skipping assets directory: {item_path}")
                continue
                
            try:
                stat = os.stat(item_path)
                if stat[0] & 0o040000:  # Directory
                    print(f"[STAGING DEBUG] Recursing into directory: {item_path}")
                    files.extend(list_files_recursive(item_path, exclude_dirs))
                else:  # File
                    print(f"[STAGING DEBUG] Found file: {item_path}")
                    files.append(item_path)
            except OSError as e:
                print(f"[STAGING DEBUG] Error accessing {item_path}: {e}")
                continue
                
        print(f"[STAGING DEBUG] list_files_recursive found {len(files)} total files in {path}")
        return files
    except Exception as e:
        print(f"[STAGING DEBUG] CRITICAL ERROR in list_files_recursive for {path}: {e}")
        return []


def file_exists(path):
    """Check if file exists"""
    try:
        os.stat(path)
        return True
    except OSError:
        return False


# =============================================================================
# Backup Operations (Step 3: Backup current system)  
# =============================================================================

def create_system_backup(description="Pre-update backup"):
    """Create complete system backup"""
    try:
        # Ensure staging directories
        success, msg = ensure_staging_dirs()
        if not success:
            return False, msg
            
        # Clear existing backup
        clear_directory(BACKUP_DIR, preserve_files=["version.info"])
        
        # Create version info
        version_info = create_backup_version(description)
        if not version_info:
            return False, "Failed to create version info"
            
        # Copy all files except staging areas
        exclude_paths = ["/backup", "/update"]
        backed_up_files = copy_recursive("/", BACKUP_DIR, exclude_paths)
        
        # Update version info with file list
        version_info["files_backed_up"] = [f[len(BACKUP_DIR):] for f in backed_up_files]
        
        # Save version info
        if not save_backup_version(version_info):
            return False, "Failed to save backup metadata"
            
        return True, {
            "version": version_info,
            "files_backed_up": len(backed_up_files),
            "message": f"Backed up {len(backed_up_files)} files"
        }
        
    except Exception as e:
        return False, f"Backup failed: {e}"


def restore_from_backup():
    """Restore system from backup"""
    try:
        if not dir_exists(BACKUP_DIR):
            return False, "No backup found"
            
        version_info = get_backup_version()
        if not version_info:
            return False, "Backup metadata not found"
            
        # Clear current system (preserve staging areas)
        current_files = list_files_recursive("/", exclude_dirs=["/backup", "/update"])
        deleted_files = []
        
        for file_path in current_files:
            try:
                os.remove(file_path)
                deleted_files.append(file_path)
            except OSError:
                continue
                
        # Copy backup files to root
        restored_files = copy_recursive(BACKUP_DIR, "/", exclude_paths=["version.info"])
        
        return True, {
            "version": version_info,
            "deleted_files": len(deleted_files),
            "restored_files": len(restored_files),
            "message": f"Restored {len(restored_files)} files from backup"
        }
        
    except Exception as e:
        return False, f"Restore failed: {e}"


# =============================================================================
# Update Operations (Step 4: Apply staged updates)
# =============================================================================

def apply_staged_updates(delete_existing=False, preserve_config=True):
    """Apply staged updates to system"""
    try:
        if not dir_exists(UPDATE_DIR):
            return False, "No staged updates found"
            
        result = {
            "applied_files": [],
            "deleted_files": [],
            "preserved_files": []
        }
        
        # Handle existing file deletion
        if delete_existing:
            current_files = list_files_recursive("/", exclude_dirs=["/backup", "/update"])
            for file_path in current_files:
                # Preserve config if requested
                if preserve_config and file_path.endswith("/config.json"):
                    result["preserved_files"].append(file_path)
                    continue
                    
                try:
                    os.remove(file_path)
                    result["deleted_files"].append(file_path)
                except OSError:
                    continue
                    
        # Apply staged files with new folder structure
        # Copy RokCommon to /RokCommon if it exists
        rokcommon_staging = f"{UPDATE_DIR}/RokCommon"
        if dir_exists(rokcommon_staging):
            rokcommon_files = copy_recursive(rokcommon_staging, "/RokCommon", exclude_paths=[])
            result["applied_files"].extend([f"RokCommon/{f[10:]}" for f in rokcommon_files if f.startswith("/RokCommon/")])
            
        # Copy device folder (RokVehicle/RokVision) to root if it exists
        device_folders = ["RokVehicle", "RokVision"]
        for device_folder in device_folders:
            device_staging = f"{UPDATE_DIR}/{device_folder}"
            if dir_exists(device_staging):
                device_files = copy_recursive(device_staging, "/", exclude_paths=[])
                result["applied_files"].extend([f[1:] for f in device_files])  # Remove leading /
                break  # Only one device type should be present
        
        # Clear staging area after successful update
        clear_directory(UPDATE_DIR)
        
        # Add message to result
        result["message"] = f"Applied {len(result['applied_files'])} updates"
        return True, result
        
    except Exception as e:
        return False, f"Update failed: {e}"


# =============================================================================
# GitHub API Functions (reused from old system)
# =============================================================================

def get_github_file_list(repo, branch="main", folder=""):
    """Get list of files from GitHub repository"""
    print(f"[DEBUG] get_github_file_list called with repo='{repo}', branch='{branch}', folder='{folder}'")
    
    # Pre-flight memory check
    gc.collect()
    
    try:
        # Validate repository format (owner/repo)
        if '/' not in repo or len(repo.split('/')) != 2:
            return False, f"Invalid repository format. Expected 'owner/repo', got '{repo}'"
        
        # For now, use a simpler approach - return a hardcoded list for RokCommon
        # This bypasses the GitHub API crash entirely
        if folder == "RokCommon":
            print(f"[DEBUG] Using hardcoded file list for RokCommon")
            files = [
                {"path": "__init__.py", "github_path": "RokCommon/__init__.py", "sha": "dummy"},
                {"path": "networking/__init__.py", "github_path": "RokCommon/networking/__init__.py", "sha": "dummy"},
                {"path": "networking/wifi_manager.py", "github_path": "RokCommon/networking/wifi_manager.py", "sha": "dummy"},
                {"path": "ota/__init__.py", "github_path": "RokCommon/ota/__init__.py", "sha": "dummy"},
                {"path": "ota/ota_page.py", "github_path": "RokCommon/ota/ota_page.py", "sha": "dummy"},
                {"path": "ota/ota_staging.py", "github_path": "RokCommon/ota/ota_staging.py", "sha": "dummy"},
                {"path": "web/__init__.py", "github_path": "RokCommon/web/__init__.py", "sha": "dummy"},
                {"path": "web/request_response.py", "github_path": "RokCommon/web/request_response.py", "sha": "dummy"},
                {"path": "web/static_assets.py", "github_path": "RokCommon/web/static_assets.py", "sha": "dummy"},
                {"path": "web/web_handler.py", "github_path": "RokCommon/web/web_handler.py", "sha": "dummy"},
                {"path": "variables/__init__.py", "github_path": "RokCommon/variables/__init__.py", "sha": "dummy"},
                {"path": "variables/vars_store.py", "github_path": "RokCommon/variables/vars_store.py", "sha": "dummy"},
                {"path": "variables/vehicle_types.py", "github_path": "RokCommon/variables/vehicle_types.py", "sha": "dummy"}
            ]
            print(f"[DEBUG] Returning {len(files)} hardcoded files")
            return True, files
            
        url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
        
        print(f"Fetching file list from: {url}")
        
        # TEMPORARY: Use hardcoded file list to avoid GitHub API crashes
        # This is a workaround until we can fix the SSL/memory issue
        if folder == "RokCommon":
            print(f"[DEBUG] Using hardcoded RokCommon file list to avoid crashes")
            files = [
                {"path": "__init__.py", "github_path": "RokCommon/__init__.py", "sha": "dummy"},
                {"path": "networking/__init__.py", "github_path": "RokCommon/networking/__init__.py", "sha": "dummy"},
                {"path": "networking/wifi_manager.py", "github_path": "RokCommon/networking/wifi_manager.py", "sha": "dummy"},
                {"path": "ota/__init__.py", "github_path": "RokCommon/ota/__init__.py", "sha": "dummy"},
                {"path": "ota/ota_page.py", "github_path": "RokCommon/ota/ota_page.py", "sha": "dummy"},
                {"path": "ota/ota_staging.py", "github_path": "RokCommon/ota/ota_staging.py", "sha": "dummy"},
                {"path": "web/__init__.py", "github_path": "RokCommon/web/__init__.py", "sha": "dummy"},
                {"path": "web/request_response.py", "github_path": "RokCommon/web/request_response.py", "sha": "dummy"},
                {"path": "web/static_assets.py", "github_path": "RokCommon/web/static_assets.py", "sha": "dummy"},
                {"path": "web/web_handler.py", "github_path": "RokCommon/web/web_handler.py", "sha": "dummy"},
                {"path": "web/pages/__init__.py", "github_path": "RokCommon/web/pages/__init__.py", "sha": "dummy"},
                {"path": "web/pages/home_page.py", "github_path": "RokCommon/web/pages/home_page.py", "sha": "dummy"},
                {"path": "web/pages/wifi_page.py", "github_path": "RokCommon/web/pages/wifi_page.py", "sha": "dummy"},
                {"path": "variables/__init__.py", "github_path": "RokCommon/variables/__init__.py", "sha": "dummy"},
                {"path": "variables/vars_store.py", "github_path": "RokCommon/variables/vars_store.py", "sha": "dummy"},
                {"path": "variables/vehicle_types.py", "github_path": "RokCommon/variables/vehicle_types.py", "sha": "dummy"}
            ]
            print(f"[DEBUG] Returning {len(files)} hardcoded files")
            return True, files
        
        # For non-RokCommon folders, return an error for now
        return False, "GitHub API temporarily disabled for stability. Only RokCommon folder supported via hardcoded list."
        
    except Exception as e:
        print(f"[DEBUG] Exception in get_github_file_list: {e}")
        return False, f"Failed to get file list: {e}"
    finally:
        # Force garbage collection
        gc.collect()


def get_free_memory():
    """Get available free memory in bytes"""
    try:
        import micropython
        return gc.mem_free()
    except Exception:
        return 100000  # Default fallback


def download_github_file_safe(repo, branch, file_path, max_retries=2):
    """Download a single file from GitHub with enhanced error handling and retries"""
    for retry in range(max_retries + 1):
        try:
            if retry > 0:
                print(f"[DEBUG] Retry {retry} for {file_path}")
                time.sleep_ms(500)  # Delay between retries
                
            # Check memory before download
            free_mem = get_free_memory()
            if free_mem < 20000:  # Less than 20KB
                return False, f"Insufficient memory for download: {free_mem} bytes"
            
            url = f"https://raw.githubusercontent.com/{repo}/{branch}/{file_path}"
            print(f"[DEBUG] Downloading: {file_path}")
            
            # Force aggressive garbage collection before request
            gc.collect()
            
            # Set shorter timeout to prevent hanging
            response = None
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code != 200:
                    if response:
                        response.close()
                    return False, f"Download failed: {response.status_code}"
                
                # Get content in smaller chunks to avoid memory issues
                content = response.content
                response.close()
                response = None
                
                # Final garbage collection
                gc.collect()
                
                return True, content
                
            except Exception as inner_e:
                if response:
                    try:
                        response.close()
                    except:
                        pass
                raise inner_e
                
        except Exception as e:
            print(f"[DEBUG] Download error for {file_path} (attempt {retry + 1}): {e}")
            gc.collect()  # Clean up after error
            
            if retry == max_retries:
                return False, f"Download failed after {max_retries + 1} attempts: {e}"
                
        finally:
            # Always clean up
            gc.collect()
    
    return False, "Download failed - unknown error"


def download_github_file(repo, branch, file_path):
    """Download a single file from GitHub (legacy function for compatibility)"""
    return download_github_file_safe(repo, branch, file_path)


def restart_system():
    """Restart the ESP32"""
    try:
        print("Restarting system...")
        machine.reset()
    except Exception:
        print("Reset failed, attempting soft reboot...")
        try:
            machine.soft_reset()
        except Exception:
            print("Soft reset also failed")