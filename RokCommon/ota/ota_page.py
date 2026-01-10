"""
Generic OTA (Over-The-Air) update page for RokCommon

Provides web UI for:
- Uploading complete project folders
- Downloading updates from GitHub
- Device restart functionality

Updated to use unified Request/Response system
"""

from RokCommon.variables.vars_store import get_config_value
from RokCommon.web import Request, Response, PageHandler
from RokCommon.web.pages.home_page import load_and_process_header
import RokCommon.ota.ota_utils as ota
import os
import gc
import ujson


# ---------------------------------------------------------
# Unified OTA Handler
# ---------------------------------------------------------
class OTAPageHandler(PageHandler):
    """OTA page handler using unified Request/Response system"""

    def handle_get(self, request):
        """Handle GET requests for OTA page"""
        try:
            html = build_ota_page()
            return Response.html(html)
        except Exception as e:
            print(f"Error in OTA handle_get: {e}")
            return Response.server_error(f"Failed to load OTA page: {e}")

    def handle_post(self, request):
        """Handle POST requests for OTA page"""
        try:
            if request.is_multipart():
                return self.handle_file_upload(request)
            else:
                return self.handle_form_post(request)
        except Exception as e:
            print(f"Error in OTA handle_post: {e}")
            return Response.json_error(
                f"Error: {e}", status="500 Internal Server Error"
            )

    def handle_file_upload(self, request):
        """Handle multipart file upload"""
        try:
            # Parse multipart form data
            boundary = request.content_type.split("boundary=")[1]
            parts = request.body.encode().split(f"--{boundary}".encode())

            uploaded_files = []
            folder_name = ""

            for part in parts:
                if b"Content-Disposition: form-data" in part:
                    lines = part.split(b"\r\n")

                    # Find the Content-Disposition line
                    for i, line in enumerate(lines):
                        if b"Content-Disposition: form-data" in line:
                            line_str = line.decode("utf-8")

                            # Extract filename
                            if "filename=" in line_str:
                                filename_start = line_str.find('filename="') + 10
                                filename_end = line_str.find('"', filename_start)
                                filename = line_str[filename_start:filename_end]

                                # Skip empty files
                                if not filename:
                                    continue

                                # Extract folder name from first file if not set
                                if not folder_name and "/" in filename:
                                    folder_name = filename.split("/")[0]

                                # Remove folder prefix for local storage
                                if folder_name and filename.startswith(
                                    folder_name + "/"
                                ):
                                    local_filename = filename[len(folder_name) + 1 :]
                                else:
                                    local_filename = filename

                                # Find the start of file content (after double CRLF)
                                content_start = -1
                                for j in range(i + 1, len(lines)):
                                    if lines[j] == b"":
                                        content_start = j + 1
                                        break

                                if content_start != -1:
                                    # Get file content (all remaining lines except the last empty one)
                                    file_content = b"\r\n".join(lines[content_start:-1])

                                    # Save the file
                                    success, msg = ota.save_uploaded_file(
                                        local_filename, file_content
                                    )
                                    if success:
                                        uploaded_files.append(local_filename)
                                        print(f"Uploaded: {local_filename}")
                                    else:
                                        print(
                                            f"Failed to upload {local_filename}: {msg}"
                                        )

            if uploaded_files:
                return Response.json_success(
                    f"Successfully uploaded {len(uploaded_files)} files",
                    files=uploaded_files,
                )
            else:
                return Response.json_error("No files were uploaded")

        except Exception as e:
            print(f"File upload error: {e}")
            return Response.json_error(
                f"Upload failed: {str(e)}", status="500 Internal Server Error"
            )

    def handle_form_post(self, request):
        """Handle regular form POST requests"""
        try:
            action = request.get_form("action", "")

            if action == "github_download":
                return self.handle_github_download(request)
            elif action == "restart":
                return self.handle_restart(request)
            elif action == "backup":
                return self.handle_backup(request)
            elif action == "restore":
                return self.handle_restore(request)
            else:
                return Response.json_error(f"Unknown action: {action}")

        except Exception as e:
            print(f"Form post error: {e}")
            return Response.json_error(
                f"Form processing failed: {str(e)}", status="500 Internal Server Error"
            )

    def handle_github_download(self, request):
        """Handle GitHub download request"""
        try:
            repo = request.get_form("repo", ota.DEFAULT_GITHUB_REPO).strip()
            branch = request.get_form("branch", ota.DEFAULT_GITHUB_BRANCH).strip()
            folder = request.get_form("folder", "").strip()

            if not repo:
                return Response.json_error("Repository name is required")

            # Perform GitHub sync
            success, result = ota.sync_from_github(repo, branch, folder)

            if success:
                return Response.json_success(
                    f"Downloaded {len(result.get('downloaded', []))} files",
                    details=result,
                )
            else:
                return Response.json_error(result, status="500 Internal Server Error")

        except Exception as e:
            return Response.json_error(
                f"GitHub download failed: {str(e)}", status="500 Internal Server Error"
            )

    def handle_restart(self, request):
        """Handle restart request"""
        try:
            # Schedule restart after response is sent
            def restart_delayed():
                import time

                time.sleep(2)
                ota.restart_system()

            import _thread

            _thread.start_new_thread(restart_delayed, ())

            return Response.json_success("System restart initiated")

        except Exception as e:
            return Response.json_error(
                f"Restart failed: {str(e)}", status="500 Internal Server Error"
            )

    def handle_backup(self, request):
        """Handle backup request"""
        try:
            success, result = ota.backup_system()

            if success:
                return Response.json_success(
                    "Backup created successfully", details=result
                )
            else:
                return Response.json_error(result, status="500 Internal Server Error")

        except Exception as e:
            return Response.json_error(
                f"Backup failed: {str(e)}", status="500 Internal Server Error"
            )

    def handle_restore(self, request):
        """Handle restore request"""
        try:
            success = ota.restore_backup()

            if success:
                return Response.json_success("Backup restored successfully")
            else:
                return Response.json_error(
                    "Restore failed", status="500 Internal Server Error"
                )

        except Exception as e:
            return Response.json_error(
                f"Restore failed: {str(e)}", status="500 Internal Server Error"
            )


# Create the handler instance
ota_handler = OTAPageHandler()


# Keep legacy functions for backward compatibility during transition
def handle_get(query_string=None):
    """Legacy GET handler for backward compatibility"""
    request = Request(method="GET", query_string=query_string or "")
    response = ota_handler.handle_get(request)
    return (response.status, response.content_type, response.body)


def handle_post(body, content_type, query_string=None):
    """Legacy POST handler for backward compatibility"""
    request = Request(
        method="POST",
        body=body,
        content_type=content_type,
        query_string=query_string or "",
    )
    response = ota_handler.handle_post(request)
    return (response.status, response.content_type, response.body)


# ---------------------------------------------------------
# HTML page building
# ---------------------------------------------------------
def build_ota_page():
    """Build the OTA page HTML using unified template with project-specific content"""
    try:
        # Load the unified OTA template from RokCommon
        template_path = "RokCommon/web/pages/assets/ota_page.html"

        try:
            with open(template_path, "r") as f:
                html_template = f.read()
        except:
            # Fallback - should not happen with proper deployment
            print("Warning: Unified OTA template not found, using basic fallback")
            html_template = "<!DOCTYPE html><html><head><title>OTA Updates</title></head><body><h1>OTA Updates</h1><p>Template not found</p></body></html>"

        # Get configuration values
        vehicle_name = get_config_value("vehicleName", "RokDevice")
        project_type = get_config_value("projectType", "unknown")

        # Load and process header navigation
        header_nav = load_and_process_header(vehicle_name, project_type)
        if not header_nav:
            header_nav = f"<div>Header not found for {vehicle_name}</div>"

        # Simple template replacement - only header needed
        html = html_template.replace("{{ header_nav }}", header_nav)

        return html

    except Exception as e:
        print(f"Error building OTA page: {e}")
        vehicle_name = get_config_value("vehicleName", "RokDevice")
        return f"<!DOCTYPE html><html><head><title>OTA Error</title></head><body><h1>Error</h1><p>Failed to load OTA page for {vehicle_name}: {e}</p></body></html>"
