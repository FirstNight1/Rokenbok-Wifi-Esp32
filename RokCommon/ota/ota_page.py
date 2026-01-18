"""
Simplified OTA Update Page Handler - Upload Only

Implements a 4-step OTA process:
1. Upload Folders (RokCommon + RokVehicle/RokVision)
2. Preview Changes (compare staged vs current)  
3. Backup Current (save to /backup with version)
4. Apply Updates (copy from /update to root)

This provides a safe update process with rollback capability.
"""

import os
from ..web.request_response import Request, Response
from ..web.pages.home_page import load_and_process_header
# Import staging module
try:
    from .ota_staging import (
        stage_folder_upload, 
        save_upload_timestamp, 
        clear_upload_timestamp,
        get_staged_summary, 
        check_upload_timing,
        clear_directory,
        UPDATE_DIR,
        file_exists,
        makedirs,
        dir_exists,
        copy_recursive,
        copy_file,
        restart_system,
        count_files_recursive
    )
    STAGING_AVAILABLE = True
except ImportError as ie:
    # Import failed, OTA functionality disabled
    STAGING_AVAILABLE = False
    raise  # Re-raise to see the actual import problem
except Exception as e:
    # Unexpected error during import
    STAGING_AVAILABLE = False
    raise  # Re-raise to see the actual problem
    
class OTAPageHandler:
    """Upload-only OTA page handler"""

    def __init__(self):
        self.busy = False  # Prevent concurrent operations

    def __call__(self, request):
        """Handle OTA page requests"""
        if request.method == "GET":
            return self.handle_get(request)
        elif request.method == "POST":
            return self.handle_post(request)
        else:
            return Response.method_not_allowed()

    def handle_get(self, request):
        """Handle GET requests - show OTA page"""
        try:
            html = self._build_ota_page()
            return Response.html(html)
        except Exception as e:
            return Response.server_error(f"OTA page error: {e}")

    def handle_post(self, request):
        """Handle POST requests for OTA actions"""
        try:
            action = request.get_form("action", "")

            # Step 1 actions
            if action == "stage_upload":
                return self.handle_stage_upload(request)
            elif action == "clear_staged":
                return self.handle_clear_staged(request)
            elif action == "validate_uploads":
                return self.handle_validate_uploads(request)
            
            # Step 2 actions  
            elif action == "preview_changes":
                return self.handle_preview_changes(request)
            
            # Step 3 actions
            elif action == "create_backup":
                return self.handle_create_backup(request)
            elif action == "restore_backup":
                return self.handle_restore_backup(request)
            
            # Step 4 actions
            elif action == "apply_updates":
                return self.handle_apply_updates(request)
            
            # System actions
            elif action == "restart":
                return self.handle_restart(request)
            else:
                return Response.json_error(f"Unknown action: {action}")

        except Exception as e:
            return Response.json_error(f"OTA operation failed: {str(e)}")

    # =================================================================
    # Step 1: Upload Staging
    # =================================================================

    def handle_validate_uploads(self, request):
        """Validate uploaded folders and timing"""
        try:
            # Staging must always be available
            
            # Validate uploads
            staged_summary = get_staged_summary()
            timing_valid, timing_msg = check_upload_timing()
            
            # Check timing and folder status
            
            return Response.json_success(
                "Upload validation complete", 
                staged_folders=staged_summary,
                timing_valid=timing_valid,
                timing_message=timing_msg
            )
        except Exception as e:
            print(f"[OTA DEBUG] Validation error: {e}")
            return Response.json_error(f"Validation failed: {str(e)}")
            
    def handle_stage_upload(self, request):
        """Handle file uploads to staging area - simplified to avoid crashes"""
        try:
            # Basic validation
            if not request.is_multipart():
                return Response.json_error("File upload requires multipart form")

            folder_type = request.get_form("folder_type", "")
            if folder_type not in ["RokCommon", "RokVehicle", "RokVision"]:
                return Response.json_error("Invalid folder type")

            is_first_batch = request.get_form("is_first_batch", "false") == "true"
            
            # Clear staging on first batch
            if is_first_batch:
                # Ensure /update exists
                try:
                    makedirs(UPDATE_DIR)
                except:
                    pass
                
                # Clear appropriate folders based on what's being uploaded
                if folder_type in ["RokVehicle", "RokVision"]:
                    # For device uploads, clear both device folders
                    print(f"[UPLOAD] First batch - clearing both RokVehicle and RokVision for {folder_type} upload")
                    for clear_folder in ["RokVehicle", "RokVision"]:
                        clear_path = f"{UPDATE_DIR}/{clear_folder}"
                        try:
                            if dir_exists(clear_path):
                                clear_directory(clear_path)
                                print(f"[UPLOAD] Cleared {clear_path}")
                            clear_upload_timestamp(clear_folder)
                        except Exception as e:
                            print(f"[UPLOAD] Clear warning for {clear_folder}: {e}")
                else:
                    # For RokCommon, only clear RokCommon
                    print(f"[UPLOAD] First batch - clearing {folder_type} only")
                    clear_path = f"{UPDATE_DIR}/{folder_type}"
                    try:
                        if dir_exists(clear_path):
                            clear_directory(clear_path)
                            print(f"[UPLOAD] Cleared {clear_path}")
                        clear_upload_timestamp(folder_type)
                    except Exception as e:
                        print(f"[UPLOAD] Clear warning for {folder_type}: {e}")
                
                # Create target directory for the folder being uploaded
                try:
                    makedirs(f"{UPDATE_DIR}/{folder_type}")
                except:
                    pass

            # Get and save files
            uploaded_files = request.get_files("files")
            if not uploaded_files:
                return Response.json_error("No files found")

            print(f"[UPLOAD] Processing {len(uploaded_files)} files for {folder_type}")
            files_saved = []
            for file_info in uploaded_files:
                filename = file_info.get('filename', '')
                content = file_info.get('content', b'')
                
                if not filename:
                    continue
                
                print(f"[UPLOAD] Processing file: {filename} ({len(content)} bytes)")
                
                try:
                    # Content should always be bytes from parser
                    if type(content) != bytes:
                        content = str(content).encode('latin-1')
                    
                    # Clean filename
                    if filename.startswith(f"{folder_type}/"):
                        filename = filename[len(folder_type) + 1:]
                    
                    target_path = f"{UPDATE_DIR}/{folder_type}/{filename}"
                    
                    parent_dir = "/".join(target_path.split("/")[:-1])
                    makedirs(parent_dir)
                    with open(target_path, "wb") as f:
                        f.write(content)
                    files_saved.append(filename)
                    print(f"[UPLOAD] Successfully saved: {filename}")
                except Exception as e:
                    print(f"[UPLOAD] Error saving {filename}: {e}")
                    continue

            # Save timestamp on final batch
            browser_timestamp = request.get_form("upload_timestamp", "")
            if browser_timestamp:
                try:
                    save_upload_timestamp(folder_type, browser_timestamp)
                except Exception as e:
                    print(f"[UPLOAD] Timestamp warning: {e}")

            # Aggressive memory cleanup
            try:
                request.clear_file_contents()
            except Exception:
                pass

            # Force multiple garbage collections
            import gc
            gc.collect()
            
            # Simple response to minimize memory usage
            return Response.json_success("Files uploaded successfully", details={"count": len(files_saved)})

        except Exception as e:
            print(f"[UPLOAD] Upload error: {e}")
            # Aggressive memory cleanup on error
            try:
                request.clear_file_contents()
            except Exception:
                pass
            import gc
            gc.collect()
            return Response.json_error(f"Upload failed: {e}")

    def handle_clear_staged(self, request):
        """Clear staged updates"""
        try:
            # Staging must always be available
            
            # Clear staged updates and timestamps
            
            # Clear staging directory
            success, result = clear_directory(UPDATE_DIR)
            if not success:
                return Response.json_error(result)
                
            # Also clear all timestamps to prevent partial uploads
            try:
                ts_path = f"{UPDATE_DIR}/.timestamps"
                if file_exists(ts_path):
                    import os
                    os.remove(ts_path)
                    pass  # Timestamps file removed
            except Exception as e:
                pass  # Error removing timestamps
                
            return Response.json_success("Staging cleared successfully")
        except Exception as e:
            print(f"[OTA DEBUG] Clear error: {e}")
            return Response.json_error(f"Clear failed: {str(e)}")

    # =================================================================
    # Step 2: Preview Changes
    # =================================================================

    def _compare_files_for_preview(self):
        """Compare staged files against current files to show diff"""
        try:
            new_files = []
            updated_files = []
            unchanged_files = []
            
            # Get staged folders
            staged_folders = ["RokCommon", "RokVehicle", "RokVision"]
            
            for folder in staged_folders:
                staged_path = f"{UPDATE_DIR}/{folder}"
                current_path = f"/{folder}"
                
                if not dir_exists(staged_path):
                    continue
                    
                # Get all files in staged folder
                staged_files = self._get_all_files_recursive(staged_path)
                
                for staged_file in staged_files:
                    # Remove the staged path prefix to get relative path
                    rel_path = staged_file.replace(f"{UPDATE_DIR}/", "")
                    current_file = f"/{rel_path}"
                    
                    if file_exists(current_file):
                        # File exists in both - check if different
                        try:
                            staged_size = os.stat(staged_file)[6]  # File size
                            current_size = os.stat(current_file)[6]
                            
                            if staged_size != current_size:
                                updated_files.append(rel_path)
                            else:
                                unchanged_files.append(rel_path)
                        except Exception:
                            # If we can't compare, assume it's updated
                            updated_files.append(rel_path)
                    else:
                        # File only exists in staging - it's new
                        new_files.append(rel_path)
            
            # Find deleted files (exist in current but not in staging)
            deleted_files = []
            for folder in staged_folders:
                current_path = f"/{folder}"
                
                if dir_exists(current_path):
                    current_files = self._get_all_files_recursive(current_path)
                    
                    for current_file in current_files:
                        # Convert to relative path
                        rel_path = current_file[1:]  # Remove leading /
                        staged_file = f"{UPDATE_DIR}/{rel_path}"
                        
                        if not file_exists(staged_file):
                            # Only count as deleted if the folder is being updated
                            folder_being_updated = rel_path.split("/")[0]
                            if dir_exists(f"{UPDATE_DIR}/{folder_being_updated}"):
                                deleted_files.append(rel_path)
            
            return {
                "new_files": new_files,
                "updated_files": updated_files, 
                "deleted_files": deleted_files,
                "unchanged_files": unchanged_files
            }
            
        except Exception as e:
            print(f"[OTA DEBUG] Error comparing files: {e}")
            return {
                "new_files": [],
                "updated_files": [], 
                "deleted_files": [],
                "unchanged_files": []
            }
    
    def _get_all_files_recursive(self, path):
        """Get all files in a directory recursively"""
        files = []
        try:
            items = os.listdir(path)
            for item in items:
                item_path = f"{path}/{item}"
                try:
                    # Check if it's a directory
                    os.listdir(item_path)
                    # It's a directory, recurse
                    files.extend(self._get_all_files_recursive(item_path))
                except OSError:
                    # It's a file
                    files.append(item_path)
        except Exception as e:
            print(f"[OTA DEBUG] Error listing files in {path}: {e}")
        return files

    def handle_preview_changes(self, request):
        """Preview staged changes with detailed file comparison"""
        try:
            if self.busy:
                return Response.json_error("Another operation is in progress, please wait")
            
            self.busy = True
            # Preview staged changes
            
            # Check that uploads are ready
            staged_summary = get_staged_summary()
            timing_valid, timing_msg = check_upload_timing()
            
            if not timing_valid:
                self.busy = False
                return Response.json_error(f"Cannot preview: {timing_msg}")
            
            # Files that are preserved during apply (won't actually be deleted)
            preserved_files = {
                "favicon.ico",
                "config.json"
            }
            
            new_files = []
            updated_files = []
            deleted_files = []
            unchanged_files = []
            
            try:
                for folder_info in staged_summary:
                    folder_name = folder_info.get("name", "")
                    if folder_name not in ["RokCommon", "RokVehicle", "RokVision"]:
                        continue
                    
                    staged_path = f"{UPDATE_DIR}/{folder_name}"
                    
                    # Determine deployment destination
                    if folder_name == "RokCommon":
                        # RokCommon stays in its subdirectory
                        current_path = f"/{folder_name}"
                    else:
                        # RokVehicle and RokVision both deploy to root directory
                        current_path = "/"
                    
                    # Compare staged vs current files
                    
                    if not dir_exists(staged_path):
                        continue
                    
                    # Get all staged files
                    staged_files = self._get_all_files_recursive(staged_path)
                    
                    for staged_file in staged_files:
                        # Convert staged file to relative path within the folder
                        rel_path = staged_file.replace(f"{UPDATE_DIR}/{folder_name}/", "")
                        
                        # Skip preserved files
                        filename = rel_path.split("/")[-1]
                        if filename in preserved_files:
                            continue
                        
                        # Determine where this file would be deployed
                        if folder_name == "RokCommon":
                            current_file = f"/{folder_name}/{rel_path}"
                        else:
                            # RokVehicle and RokVision deploy to root
                            current_file = f"/{rel_path}"
                        
                        if file_exists(current_file):
                            # File exists - check if different
                            try:
                                staged_size = os.stat(staged_file)[6]
                                current_size = os.stat(current_file)[6]
                                
                                if staged_size != current_size:
                                    updated_files.append(f"{folder_name}/{rel_path}")
                                else:
                                    unchanged_files.append(f"{folder_name}/{rel_path}")
                            except Exception:
                                # If can't compare, assume updated
                                updated_files.append(f"{folder_name}/{rel_path}")
                        else:
                            # New file
                            new_files.append(f"{folder_name}/{rel_path}")
                    
                    # Find deleted files (exist currently but not in staging)
                    if dir_exists(current_path):
                        current_files = self._get_all_files_recursive(current_path)
                        # Find deleted files
                        
                        for current_file in current_files:
                            # Convert current file to relative path
                            if folder_name == "RokCommon":
                                # For RokCommon, remove /RokCommon/ prefix
                                prefix = f"/{folder_name}/"
                                if current_file.startswith(prefix):
                                    rel_path = current_file[len(prefix):]
                                else:
                                    continue  # Skip files not in RokCommon folder
                            else:
                                # For RokVehicle/RokVision, files are in root
                                # But we need to exclude RokCommon files and preserved files
                                if current_file.startswith("/RokCommon/"):
                                    continue  # Skip RokCommon files
                                rel_path = current_file[1:] if current_file.startswith("/") else current_file
                            
                            # Skip preserved files
                            filename = rel_path.split("/")[-1] 
                            if filename in preserved_files:
                                continue
                            
                            # Check if this file exists in staging
                            staged_file = f"{staged_path}/{rel_path}"
                            if not file_exists(staged_file):
                                deleted_files.append(f"{folder_name}/{rel_path}")
                
                self.busy = False
                return Response.json_success("Preview generated", 
                                           new_files=new_files,
                                           updated_files=updated_files,
                                           deleted_files=deleted_files,
                                           unchanged_files=unchanged_files,
                                           staged_folders=staged_summary)
                
            except Exception as e:
                self.busy = False
                return Response.json_error(f"Detailed preview failed: {str(e)}")
                
        except Exception as e:
            self.busy = False
            return Response.json_error(f"Preview failed: {str(e)}")

    # =================================================================
    # Step 3: Backup Operations
    # =================================================================


    def handle_create_backup(self, request):
        """Create system backup - RokCommon always, device folders only if being updated"""
        try:
            if self.busy:
                return Response.json_error("Another operation is in progress, please wait")
            
            self.busy = True
            backup_dir = "/backup"
            makedirs(backup_dir)
            backed_up = []
            
            # Always backup RokCommon
            src = "/RokCommon"
            dst = f"{backup_dir}/RokCommon"
            if dir_exists(src):
                # Clear destination if it exists, then recreate
                if dir_exists(dst):
                    success, msg = clear_directory(dst)
                    if not success:
                        pass  # Warning clearing, continue anyway
                    
                # Ensure clean destination exists
                makedirs(dst)
                
                # Copy files with error handling
                try:
                    copy_recursive(src, dst)
                    backed_up.append("RokCommon")
                except Exception as e:
                    self.busy = False
                    return Response.json_error(f"Failed to backup RokCommon: {str(e)}")
            
            # Determine which device folders to backup based on what's staged for update
            staged_summary = get_staged_summary()
            device_folders_to_backup = []
            
            for folder_info in staged_summary:
                if folder_info["name"] in ["RokVehicle", "RokVision"]:
                    device_folders_to_backup.append(folder_info["name"])
            
            # If no specific device folders are staged, backup the current device type
            if not device_folders_to_backup:
                # Try to determine current device type by what exists
                if dir_exists("/RokVision"):
                    device_folders_to_backup.append("RokVision")
                elif dir_exists("/RokVehicle"):
                    device_folders_to_backup.append("RokVehicle")
            
            # Backup device folders
            for folder in device_folders_to_backup:
                src = f"/{folder}"
                dst = f"{backup_dir}/{folder}"
                if dir_exists(src):
                    # Clear destination if it exists, then recreate
                    if dir_exists(dst):
                        success, msg = clear_directory(dst)
                        if not success:
                            pass  # Warning clearing, continue anyway
                    
                    # Ensure clean destination exists
                    makedirs(dst)
                    
                    # Copy files with error handling
                    try:
                        copy_recursive(src, dst)
                        backed_up.append(folder)
                    except Exception as e:
                        self.busy = False
                        return Response.json_error(f"Failed to backup {folder}: {str(e)}")
            
            if backed_up:
                self.busy = False
                return Response.json_success("Backup created", folders=backed_up)
            else:
                self.busy = False
                return Response.json_error("No folders were backed up")
        except Exception as e:
            self.busy = False
            return Response.json_error(f"Backup failed: {str(e)}")

    def handle_restore_backup(self, request):
        """Restore from backup with optional config-only mode"""
        try:
            restore_type = request.get_form("restore_type", "full")
            backup_dir = "/backup"
            restored = []
            
            if restore_type == "config_only":
                # Restore only config.json files
                config_files = [
                    "/RokCommon/variables/config.json",
                    "/RokVehicle/variables/config.json", 
                    "/RokVision/variables/config.json"
                ]
                
                for config_path in config_files:
                    backup_config = f"{backup_dir}{config_path}"
                    if file_exists(backup_config):
                        try:
                            # Ensure target directory exists
                            target_dir = "/".join(config_path.split("/")[:-1])
                            makedirs(target_dir)
                            # Copy the config file
                            copy_file(backup_config, config_path)
                            restored.append(config_path)
                        except Exception as e:
                            pass  # Error restoring config
                
                if restored:
                    return Response.json_success("Config files restored", config_files=restored)
                else:
                    return Response.json_error("No config files were restored")
            
            else:
                # Full restore
                folders = ["RokCommon", "RokVehicle", "RokVision"]
                for folder in folders:
                    src = f"{backup_dir}/{folder}"
                    dst = f"/{folder}"
                    if dir_exists(src):
                        makedirs(dst)  # Ensure destination exists
                        # Clear destination safely
                        if dir_exists(dst):
                            success, msg = clear_directory(dst)
                            if not success:
                                pass  # Warning clearing
                        # Copy files
                        try:
                            copy_recursive(src, dst)
                            restored.append(folder)
                        except Exception as e:
                            return Response.json_error(f"Failed to restore {folder}: {str(e)}")
                
                if restored:
                    return Response.json_success("System restored", folders=restored)
                else:
                    return Response.json_error("No folders were restored")
        except Exception as e:
            return Response.json_error(f"Restore failed: {str(e)}")

    def handle_apply_updates(self, request):
        """Apply staged updates"""
        try:
            # Staging must always be available
            
            # Validate that uploads are ready before applying
            timing_valid, timing_msg = check_upload_timing()
            if not timing_valid:
                return Response.json_error(f"Cannot apply updates: {timing_msg}")
            delete_existing = request.get_form("delete_existing", "false") == "true"
            preserve_config = request.get_form("preserve_config", "false") == "true"
            
            folders = ["RokCommon", "RokVehicle", "RokVision"]
            updated = []
            for folder in folders:
                src = f"{UPDATE_DIR}/{folder}"
                dst = f"/{folder}"
                if dir_exists(src):
                    if delete_existing:
                        print(f"[OTA DEBUG] Deleting existing {dst}")
                        # Preserve important files before deleting
                        preserved_files = {}
                        if preserve_config:
                            # Preserve config.json files
                            config_paths = [f"{dst}/config.json", f"{dst}/variables/config.json"]
                            for config_path in config_paths:
                                if file_exists(config_path):
                                    try:
                                        with open(config_path, 'r') as f:
                                            preserved_files[config_path] = f.read()
                                    except Exception as e:
                                        pass  # Could not preserve config
                        
                        # Always preserve favicon.ico (not updated via OTA)
                        favicon_paths = [f"{dst}/web/pages/assets/favicon.ico", f"{dst}/assets/favicon.ico"]
                        for favicon_path in favicon_paths:
                            if file_exists(favicon_path):
                                try:
                                    with open(favicon_path, 'rb') as f:
                                        preserved_files[favicon_path] = f.read()
                                except Exception as e:
                                    pass  # Could not preserve favicon
                        
                        clear_directory(dst)
                        
                        # Restore preserved files
                        for file_path, content in preserved_files.items():
                            try:
                                parent_dir = "/".join(file_path.split("/")[:-1])
                                makedirs(parent_dir)
                                if file_path.endswith('.ico'):
                                    with open(file_path, 'wb') as f:
                                        f.write(content)
                                else:
                                    with open(file_path, 'w') as f:
                                        f.write(content)
                            except Exception as e:
                                pass  # Could not restore file
                    
                    makedirs(dst)
                    copy_recursive(src, dst)
                    updated.append(folder)
            return Response.json_success("Updates applied", {"folders": updated})
        except Exception as e:
            return Response.json_error(f"Update failed: {str(e)}")

    def handle_restart(self, request):
        """Restart the system"""
        try:
            # Staging must always be available
            restart_system()
            return Response.json_success("System restarting...")
        except Exception as e:
            return Response.json_error(f"Restart failed: {str(e)}")

    # =================================================================
    # Helper Functions
    # =================================================================

    def _build_ota_page(self):
        """Build the OTA page HTML using template"""
        try:
            # Import static assets utility
            from ..web.static_assets import load_template
            
            # Load header
            header_html = load_and_process_header()
            
            # Get current status
            try:
                staged_summary = get_staged_summary()
                timing_valid, timing_msg = check_upload_timing()
            except Exception as e:
                staged_summary = []
                timing_valid = False
                timing_msg = f"Error getting status: {e}"
            
            # Load the HTML template - use relative path from filesystem root
            template_path = "RokCommon/web/pages/assets/ota_page.html"
            template_html = load_template(template_path)
            
            if not template_html:
                return f"""
<!DOCTYPE html>
<html>
<head>
    <title>OTA Debug - Template Failed</title>
    <meta charset="UTF-8">
</head>
<body>
    <h1>Template Loading Failed</h1>
    <p>Could not load template at {template_path}</p>
</body>
</html>"""
            
            # Generate staged summary HTML with improved formatting
            staged_summary_html = ''.join([
                f"<p><strong>{folder['name']}</strong>: {folder['file_count']} files - {folder['upload_status']}</p>"
                for folder in staged_summary
            ])
            
            if not staged_summary_html:
                staged_summary_html = "<p><em>No folders staged</em></p>"
            
            # Determine step classes and states
            if timing_valid:
                step2_class = ""
                step2_disabled = ""
                # Enable step 4 if preview is available (timing is valid)
                step4_class = ""
                step4_disabled = ""
            else:
                step2_class = "disabled"
                step2_disabled = "disabled"
                step4_class = "disabled"
                step4_disabled = "disabled"

            # Status classes
            staged_status_class = "ready" if timing_valid else "empty"
            staged_status_text = f"{len(staged_summary)} folders staged" if timing_valid else "No folders staged"
            timing_status_class = "valid" if timing_valid else "invalid"
            
            # Substitute template variables
            page_html = template_html.replace("{{ header_nav }}", header_html)
            page_html = page_html.replace("{{ staged_status_class }}", staged_status_class)
            page_html = page_html.replace("{{ staged_status_text }}", staged_status_text)
            page_html = page_html.replace("{{ timing_message }}", timing_msg)
            page_html = page_html.replace("{{ staged_summary_html }}", staged_summary_html)
            page_html = page_html.replace("{{ timing_status_class }}", timing_status_class)
            page_html = page_html.replace("{{ step2_class }}", step2_class)
            page_html = page_html.replace("{{ step2_disabled }}", step2_disabled)
            page_html = page_html.replace("{{ step3_class }}", step2_class)  # Step 3 follows step 2
            page_html = page_html.replace("{{ step3_disabled }}", step2_disabled)
            page_html = page_html.replace("{{ step4_class }}", step4_class)
            page_html = page_html.replace("{{ step4_disabled }}", step4_disabled)
            
            return page_html
            
        except Exception as e:
            print(f"Template error: {e}")
            return f"<html><body><h1>Template Error</h1><p>{e}</p></body></html>"

    def _get_all_files_recursive(self, path):
        """Get all files recursively from a directory"""
        files = []
        try:
            for item in os.listdir(path):
                item_path = f"{path}/{item}"
                try:
                    stat = os.stat(item_path)
                    if stat[0] & 0o040000:  # Directory
                        files.extend(self._get_all_files_recursive(item_path))
                    else:  # File
                        files.append(item_path)
                except OSError:
                    continue  # Skip items we can't stat
        except OSError:
            pass  # Skip directories we can't list
        return files


# Create the handler instance for import
try:
    ota_handler = OTAPageHandler()
except Exception as e:
    # Create a dummy handler to prevent import errors
    class DummyHandler:
        def __call__(self, request):
            return Response.json_error("OTA handler failed to initialize")
    ota_handler = DummyHandler()
