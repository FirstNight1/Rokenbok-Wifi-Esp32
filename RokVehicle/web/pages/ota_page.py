"""
Simplified OTA (Over-The-Air) update page for RokVehicle web interface

Provides web UI for:
- Uploading complete RokVehicle folders
- Downloading updates from GitHub
- Device restart functionality
"""

from variables.vars_store import load_config, save_config
import lib.ota_utils as ota
import os
import gc
import ujson


def handle_get(query_string=None):
    """Handle GET requests for OTA page"""
    try:
        cfg = load_config()

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

        # Always return (cfg, redirect, json_response)
        if action == "upload_folder":
            json_response = handle_folder_upload(fields, body, cfg)
            return cfg, None, json_response
        elif action == "github_preview":
            json_response = handle_github_preview_post(fields, cfg)
            return cfg, None, json_response
        elif action == "github_download":
            json_response = handle_github_download(fields, cfg)
            return cfg, None, json_response
        elif action == "restart":
            json_response = handle_restart(cfg)
            return cfg, None, json_response
        else:
            return cfg, "/ota?error=unknown_action", None

    except Exception as e:
        print(f"Error in OTA handle_post: {e}")
        return cfg, f"/ota?error=post_error_{e}", None


def parse_form_data(body):
    """Parse form-encoded data from POST body"""
    fields = {}

    # Handle multipart form data (for file uploads)
    if "Content-Type: multipart/form-data" in body or "form-data" in body:
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
    """Enhanced multipart form data parser for folder uploads"""
    fields = {}
    uploaded_files = []

    try:
        # Split by boundary
        if "--" not in body:
            return fields

        parts = body.split("--")

        for part in parts[1:-1]:  # Skip first empty part and last closing part
            if "Content-Disposition: form-data" not in part:
                continue

            # Split headers from content
            if "\r\n\r\n" in part:
                headers, content = part.split("\r\n\r\n", 1)
            else:
                continue

            # Parse Content-Disposition header
            disp_line = ""
            for line in headers.split("\r\n"):
                if "Content-Disposition" in line:
                    disp_line = line
                    break

            if not disp_line:
                continue

            # Extract field name
            if 'name="' not in disp_line:
                continue

            name = disp_line.split('name="')[1].split('"')[0]

            # Check if this is a file field
            if 'filename="' in disp_line:
                filename = disp_line.split('filename="')[1].split('"')[0]
                if filename:  # Only process files with names
                    # Clean up content (remove trailing boundary markers)
                    content = content.rstrip("\r\n-")
                    uploaded_files.append({"filename": filename, "content": content})
            else:
                # Regular form field
                content = content.rstrip("\r\n-")
                fields[name] = content

        if uploaded_files:
            fields["uploaded_files"] = uploaded_files

    except Exception as e:
        print(f"Multipart parsing error: {e}")

    return fields


def handle_folder_upload(fields, body, cfg):
    """Handle folder upload with multiple files"""
    try:
        uploaded_files = fields.get("uploaded_files", [])

        if not uploaded_files:
            return ujson.dumps({"success": False, "message": "No files uploaded"})

        print(f"Processing {len(uploaded_files)} uploaded files...")

        success_count = 0
        error_count = 0
        errors = []

        for file_info in uploaded_files:
            filename = file_info["filename"]
            content = file_info["content"]

            try:
                # Determine target path (maintain folder structure)
                target_path = filename
                if "/" in filename:
                    # Ensure directory exists
                    dir_path = "/".join(filename.split("/")[:-1])
                    try:
                        os.makedirs(dir_path)
                    except:
                        pass  # Directory might already exist

                # Save file
                with open(target_path, "w") as f:
                    f.write(content)

                success_count += 1
                print(f"✓ Saved: {target_path}")

            except Exception as e:
                error_count += 1
                error_msg = f"Failed to save {filename}: {e}"
                errors.append(error_msg)
                print(f"✗ {error_msg}")

        # Cleanup memory
        gc.collect()

        if success_count > 0:
            message = f"Successfully uploaded {success_count} files"
            if error_count > 0:
                message += f" ({error_count} failed)"
            return ujson.dumps({"success": True, "message": message})
        else:
            return ujson.dumps(
                {
                    "success": False,
                    "message": f"All uploads failed: {'; '.join(errors[:3])}",
                }
            )

    except Exception as e:
        return ujson.dumps({"success": False, "message": f"Upload error: {e}"})


def handle_github_preview_post(fields, cfg):
    """Handle GitHub preview request"""
    try:
        repo = fields.get("repo", "").strip()
        ref = fields.get("ref", "main").strip()
        folder = fields.get("folder", "RokVehicle").strip()
        path_filter = fields.get("path_filter", "").strip()

        if not repo:
            return ujson.dumps({"success": False, "message": "Repository required"})

        # Use OTA utils to preview GitHub files
        success, result = ota.preview_github_files(repo, ref, folder, path_filter)

        if success:
            return ujson.dumps(
                {
                    "success": True,
                    "files": result,
                    "message": f"Found {len(result)} files",
                }
            )
        else:
            return ujson.dumps({"success": False, "message": result})

    except Exception as e:
        return ujson.dumps({"success": False, "message": f"Preview error: {e}"})


def handle_github_download(fields, cfg):
    """Handle GitHub download request"""
    try:
        repo = fields.get("repo", "").strip()
        ref = fields.get("ref", "main").strip()
        folder = fields.get("folder", "RokVehicle").strip()
        path_filter = fields.get("path_filter", "").strip()

        if not repo:
            return ujson.dumps({"success": False, "message": "Repository required"})

        print(f"Downloading from GitHub: {repo}/{folder} (ref: {ref})")

        # Use OTA utils to download from GitHub
        success, result = ota.download_from_github(repo, ref, folder, path_filter)

        if success:
            return ujson.dumps(
                {
                    "success": True,
                    "message": f"Successfully downloaded {result} files from GitHub",
                }
            )
        else:
            return ujson.dumps({"success": False, "message": result})

    except Exception as e:
        return ujson.dumps({"success": False, "message": f"Download error: {e}"})


def handle_restart(cfg):
    """Handle device restart request"""
    try:
        print("Restart requested via OTA page")

        # Import and call restart function
        import machine

        # Return success response before restart
        response = ujson.dumps({"success": True, "message": "Device restarting..."})

        # Schedule restart after a short delay to allow response to be sent
        def delayed_restart():
            import utime

            utime.sleep(2)
            machine.reset()

        # Note: This is a simplified restart - in practice you might want
        # to use a timer or other mechanism for proper cleanup
        try:
            import _thread

            _thread.start_new_thread(delayed_restart, ())
        except:
            # Fallback: immediate restart
            machine.reset()

        return response

    except Exception as e:
        return ujson.dumps({"success": False, "message": f"Restart failed: {e}"})


def build_ota_page(cfg):
    """Build the OTA page HTML"""
    try:
        from web.web_server import _load_template

        # Load header navigation
        header_nav = _load_template("web/pages/assets/header_nav.html")
        if not header_nav:
            header_nav = f"<div style='background:#222;color:#fff;padding:12px;text-align:center'>Rokenbok Vehicle Control<br><span style='color:#f9e79f'>{cfg.get('vehicleName', 'RokVehicle')}</span></div>"
        else:
            header_nav = header_nav.replace(
                "{{ vehicle_name }}", cfg.get("vehicleName", "RokVehicle")
            )

        # Load main OTA template
        html = _load_template("web/pages/assets/ota_page.html")
        if html:
            html = html.replace("{{ header_nav }}", header_nav)
        else:
            html = f"<html><body><h2>Error loading OTA page template</h2></body></html>"

        # Cleanup for GC
        gc.collect()
        return html

    except Exception as e:
        print(f"OTA page template error: {e}")
        return f"<html><body><h2>OTA template error: {e}</h2></body></html>"


def extract_param(query_string, param_name):
    """Extract parameter from query string"""
    for param in query_string.split("&"):
        if "=" in param:
            key, value = param.split("=", 1)
            if key == param_name:
                return value.replace("+", " ").replace("%20", " ")
    return ""
