"""
OTA (Over-The-Air) update page for RokVehicle web interface

Provides web UI for:
- Viewing current system files
- Uploading new files
- Downloading updates from GitHub
- Managing backups and system restart
"""

from variables.vars_store import load_config, save_config
import lib.ota_utils as ota
import os
import gc


def handle_get(query_string=None):
    """Handle GET requests for OTA page"""
    try:
        cfg = load_config()

        # Handle AJAX requests for file operations
        if query_string:
            if "action=list_files" in query_string:
                return handle_list_files()
            elif "action=file_info" in query_string:
                filename = extract_param(query_string, "file")
                return handle_file_info(filename)
            elif "action=download_file" in query_string:
                filename = extract_param(query_string, "file")
                return handle_download_file(filename)
            elif "action=github_preview" in query_string:
                github_url = extract_param(query_string, "url")
                return handle_github_preview(github_url)

        # Render main OTA page
        html = build_ota_page(cfg)
        return ("200 OK", "text/html", html)

    except Exception as e:
        print(f"Error in OTA handle_get: {e}")
        return (
            "500 Internal Server Error",
            "text/html",
            f"<html><body><h2>OTA page error: {e}</h2></body></html>",
        )


def handle_post(body, cfg):
    """Handle POST requests for OTA operations"""
    try:
        # Parse form data
        fields = parse_form_data(body)
        action = fields.get("action", "")

        # Handle different actions
        if action == "upload_file":
            return handle_file_upload(fields, cfg)
        elif action == "delete_file":
            return handle_file_delete(fields, cfg)
        elif action == "github_sync":
            return handle_github_sync(fields, cfg)
        elif action == "create_backup":
            return handle_create_backup(cfg)
        elif action == "restore_backup":
            return handle_restore_backup(cfg)
        elif action == "restart_system":
            return handle_restart_system(cfg)
        elif action == "save_settings":
            return handle_save_settings(fields, cfg)
        else:
            return cfg, "/ota?error=unknown_action"

    except Exception as e:
        print(f"Error in OTA handle_post: {e}")
        return cfg, f"/ota?error=post_error_{e}"


def parse_form_data(body):
    """Parse form-encoded data from POST body"""
    fields = {}

    # Handle multipart form data (for file uploads) vs URL-encoded
    if "Content-Type: multipart/form-data" in body or "\r\n\r\n" in body:
        # Simple multipart parsing for file uploads
        fields = parse_multipart_data(body)
    else:
        # Standard URL-encoded form data
        for pair in body.split("&"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                # URL decode
                key = key.replace("+", " ").replace("%20", " ")
                value = value.replace("+", " ").replace("%20", " ")
                fields[key] = value

    return fields


def parse_multipart_data(body):
    """Basic multipart form data parser for file uploads"""
    fields = {}

    try:
        # This is a simplified parser - in a real implementation you'd want
        # a more robust multipart parser, but for basic file upload this works
        parts = body.split("\r\n\r\n")

        for part in parts:
            if "Content-Disposition: form-data" in part:
                lines = part.split("\r\n")

                # Extract field name
                disp_line = [l for l in lines if "Content-Disposition" in l][0]
                if 'name="' in disp_line:
                    name = disp_line.split('name="')[1].split('"')[0]

                    # Get field value (last line typically)
                    if lines:
                        value = lines[-1] if lines[-1] else ""
                        fields[name] = value

                        # Special handling for filename
                        if 'filename="' in disp_line:
                            filename = disp_line.split('filename="')[1].split('"')[0]
                            fields["uploaded_filename"] = filename
                            fields["file_content"] = value

    except Exception as e:
        print(f"Multipart parsing error: {e}")

    return fields


def handle_file_upload(fields, cfg):
    """Handle file upload"""
    try:
        filename = fields.get("filename", "").strip()
        content = fields.get("file_content", "")

        if not filename:
            return cfg, "/ota?error=no_filename"

        if not content:
            return cfg, "/ota?error=no_content"

        success, message = ota.save_uploaded_file(filename, content)

        if success:
            return cfg, "/ota?success=file_uploaded"
        else:
            return cfg, f"/ota?error=upload_failed_{message}"

    except Exception as e:
        return cfg, f"/ota?error=upload_error_{e}"


def handle_file_delete(fields, cfg):
    """Handle file deletion"""
    try:
        filename = fields.get("filename", "").strip()

        if not filename:
            return cfg, "/ota?error=no_filename"

        if ota.delete_file(filename):
            return cfg, "/ota?success=file_deleted"
        else:
            return cfg, "/ota?error=delete_failed"

    except Exception as e:
        return cfg, f"/ota?error=delete_error_{e}"


def handle_github_sync(fields, cfg):
    """Handle GitHub synchronization"""
    try:
        github_url = fields.get("github_url", "").strip()
        dry_run = "dry_run" in fields

        if not github_url:
            # Use default from config
            github_url = cfg.get(
                "ota_github_url",
                f"https://github.com/{ota.DEFAULT_GITHUB_REPO}/tree/{ota.DEFAULT_GITHUB_BRANCH}/{ota.DEFAULT_GITHUB_FOLDER}",
            )

        # Validate and parse URL
        valid, result = ota.validate_github_url(github_url)
        if not valid:
            return cfg, f"/ota?error=invalid_url_{result}"

        repo, branch, folder = result

        # Perform sync
        success, results = ota.sync_from_github(repo, branch, folder, dry_run)

        if success:
            if dry_run:
                # Store preview results in config temporarily
                cfg["ota_preview_results"] = results
                save_config(cfg)
                return cfg, "/ota?success=preview_ready"
            else:
                return cfg, "/ota?success=sync_completed"
        else:
            return cfg, f"/ota?error=sync_failed_{results}"

    except Exception as e:
        return cfg, f"/ota?error=github_error_{e}"


def handle_create_backup(cfg):
    """Create system backup"""
    try:
        success, result = ota.backup_system()

        if success:
            return cfg, "/ota?success=backup_created"
        else:
            return cfg, f"/ota?error=backup_failed_{result}"

    except Exception as e:
        return cfg, f"/ota?error=backup_error_{e}"


def handle_restore_backup(cfg):
    """Restore from backup"""
    try:
        success = ota.restore_backup()

        if success:
            return cfg, "/ota?success=backup_restored"
        else:
            return cfg, "/ota?error=restore_failed"

    except Exception as e:
        return cfg, f"/ota?error=restore_error_{e}"


def handle_restart_system(cfg):
    """Restart the system"""
    try:
        # Trigger restart after a short delay
        ota.restart_system()
        return cfg, "/ota?success=restarting"

    except Exception as e:
        return cfg, f"/ota?error=restart_error_{e}"


def handle_save_settings(fields, cfg):
    """Save OTA settings"""
    try:
        cfg["ota_github_url"] = fields.get("github_url", "").strip()
        cfg["ota_auto_backup"] = "auto_backup" in fields

        save_config(cfg)
        return cfg, "/ota?success=settings_saved"

    except Exception as e:
        return cfg, f"/ota?error=settings_error_{e}"


def handle_list_files():
    """Return JSON list of files for AJAX request"""
    try:
        files = ota.list_files_recursive()
        file_list = []

        for file_path in files:
            info = ota.get_file_info(file_path)
            file_list.append(
                {
                    "path": file_path,
                    "size": info["size"],
                    "size_formatted": ota.format_file_size(info["size"]),
                }
            )

        import ujson

        return ("200 OK", "application/json", ujson.dumps({"files": file_list}))

    except Exception as e:
        import ujson

        return (
            "500 Internal Server Error",
            "application/json",
            ujson.dumps({"error": str(e)}),
        )


def handle_file_info(filename):
    """Return file information for AJAX request"""
    try:
        if not filename:
            raise ValueError("No filename provided")

        info = ota.get_file_info(filename)

        import ujson

        return ("200 OK", "application/json", ujson.dumps(info))

    except Exception as e:
        import ujson

        return (
            "500 Internal Server Error",
            "application/json",
            ujson.dumps({"error": str(e)}),
        )


def handle_download_file(filename):
    """Serve file download"""
    try:
        if not filename or not ota.file_exists(filename):
            return ("404 Not Found", "text/plain", "File not found")

        # Read file content
        with open(filename, "r") as f:
            content = f.read()

        return ("200 OK", "application/octet-stream", content)

    except Exception as e:
        return ("500 Internal Server Error", "text/plain", str(e))


def handle_github_preview(github_url):
    """Preview files that would be downloaded from GitHub"""
    try:
        if not github_url:
            raise ValueError("No GitHub URL provided")

        valid, result = ota.validate_github_url(github_url)
        if not valid:
            raise ValueError(f"Invalid URL: {result}")

        repo, branch, folder = result
        success, files = ota.get_github_file_list(repo, branch, folder)

        if not success:
            raise ValueError(f"Failed to get file list: {files}")

        import ujson

        return ("200 OK", "application/json", ujson.dumps({"files": files}))

    except Exception as e:
        import ujson

        return (
            "500 Internal Server Error",
            "application/json",
            ujson.dumps({"error": str(e)}),
        )


def build_ota_page(cfg):
    """Build the OTA management page HTML"""
    try:
        # Load header navigation
        vehicle_name = cfg.get("vehicleName", "")

        try:
            # Use template caching - import here to avoid circular import
            from web.web_server import _load_template

            header_nav = _load_template("web/pages/assets/header_nav.html")
            if not header_nav:
                raise Exception("Header template not found")
            header_nav = header_nav.replace("{{ vehicle_name }}", vehicle_name)
        except Exception:
            header_nav = f"<div style='background:#222;color:#fff;padding:12px;text-align:center'>RokVehicle OTA Control<br><span style='color:#f9e79f'>{vehicle_name}</span></div>"

        # Now that we have more memory, use the improved template interface with caching
        try:
            from web.web_server import _load_template

            html = _load_template("web/pages/assets/ota_page.html")
            if not html:
                raise Exception("OTA template not found")
        except Exception as e:
            print(f"Failed to load OTA template, using fallback: {e}")
            html = build_fallback_ota_html()

        # Replace template variables
        github_url = cfg.get(
            "ota_github_url",
            f"https://github.com/{ota.DEFAULT_GITHUB_REPO}/tree/{ota.DEFAULT_GITHUB_BRANCH}/{ota.DEFAULT_GITHUB_FOLDER}",
        )
        auto_backup = cfg.get("ota_auto_backup", True)

        # Get system info
        try:
            memory_info = (
                f"Free: {gc.mem_free()} bytes"
                if hasattr(gc, "mem_free")
                else "Memory info unavailable"
            )
        except:
            memory_info = "Memory info unavailable"

        replacements = {
            "{{ header_nav }}": header_nav,
            "{{ vehicle_name }}": vehicle_name,
            "{{ github_url }}": github_url,
            "{{ auto_backup_checked }}": "checked" if auto_backup else "",
            "{{ memory_info }}": memory_info,
        }

        for placeholder, value in replacements.items():
            html = html.replace(placeholder, value)

        return html

    except Exception as e:
        print(f"Error building OTA page: {e}")
        return f"<html><body><h2>Error building OTA page: {e}</h2></body></html>"


def build_fallback_ota_html():
    """Fallback HTML if template file is missing"""
    return """
    <html>
    <head>
        <title>RokVehicle OTA Updates</title>
        <style>
            body { font-family: Arial; margin: 0; padding: 0; }
            .section { border: 1px solid #ccc; padding: 15px; margin: 15px 20px; border-radius: 5px; }
            .button { background: #007bff; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; margin: 5px; }
            .button:hover { background: #0056b3; }
            .danger { background: #dc3545; }
            .danger:hover { background: #c82333; }
            .success { color: green; }
            .error { color: red; }
            input[type="text"], input[type="file"] { width: 300px; padding: 8px; margin: 5px; }
            textarea { width: 500px; }
        </style>
    </head>
    <body>
        {{ header_nav }}
        
        <div style="max-width: 800px; margin: 20px auto;">
            <h1>RokVehicle OTA Updates</h1>
            <p><strong>Note:</strong> Using simplified OTA interface to save memory.</p>
            
            <div class="section">
                <h2>File Upload</h2>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_file">
                    <input type="text" name="filename" placeholder="Filename (e.g., main.py)" required><br>
                    <textarea name="file_content" rows="10" placeholder="File content..."></textarea><br>
                    <button type="submit" class="button">Upload File</button>
                </form>
            </div>
            
            <div class="section">
                <h2>GitHub Sync</h2>
                <form method="POST">
                    <input type="hidden" name="action" value="github_sync">
                    <input type="text" name="github_url" placeholder="GitHub URL" value="{{ github_url }}"><br>
                    <button type="submit" class="button">Sync from GitHub</button>
                    <button type="submit" name="dry_run" value="1" class="button">Preview Changes</button>
                </form>
            </div>
            
            <div class="section">
                <h2>System Management</h2>
                <form method="POST" style="display: inline;">
                    <input type="hidden" name="action" value="create_backup">
                    <button type="submit" class="button">Create Backup</button>
                </form>
                
                <form method="POST" style="display: inline;">
                    <input type="hidden" name="action" value="restore_backup">
                    <button type="submit" class="button">Restore Backup</button>
                </form>
                
                <form method="POST" style="display: inline;">
                    <input type="hidden" name="action" value="restart_system">
                    <button type="submit" class="button danger" onclick="return confirm('Really restart system?')">Restart System</button>
                </form>
            </div>
            
            <div class="section">
                <h2>System Info</h2>
                <p>{{ memory_info }}</p>
            </div>
        </div>
    </body>
    </html>
    """


def extract_param(query_string, param_name):
    """Extract parameter value from query string"""
    try:
        for part in query_string.split("&"):
            if "=" in part:
                key, value = part.split("=", 1)
                if key == param_name:
                    return value.replace("+", " ").replace("%20", " ")
    except:
        pass
    return ""
