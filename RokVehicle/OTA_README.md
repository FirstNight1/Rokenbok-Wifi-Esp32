# RokVehicle OTA (Over-The-Air) Update System

This OTA update system allows you to remotely update your RokVehicle ESP32 firmware without needing a USB connection. You can upload files through a web interface or sync directly from GitHub.

## Features

- 🌐 **Web-based file management** - Upload, download, and delete files through the web interface
- 🐙 **GitHub integration** - Sync entire project from GitHub repository
- 💾 **Automatic backup system** - Creates backups before updates with rollback capability  
- 🔒 **Safe operations** - Validates files and provides preview before applying changes
- 📱 **Mobile-friendly UI** - Responsive design works on phones and tablets
- ⚡ **Memory efficient** - Designed for ESP32 constraints with garbage collection

## How to Use

### 1. Access the OTA Interface

1. Connect to your RokVehicle web interface (usually `http://192.168.x.x`)
2. Click "OTA Updates" in the navigation menu
3. You'll see the OTA management dashboard

### 2. Upload Individual Files

1. Go to the "File Upload" section
2. Enter the file path (e.g., `main.py` or `web/pages/new_page.py`)
3. Paste the file content in the text area
4. Click "Upload File"

**Note**: The file path should include the complete directory structure where you want the file to be saved.

### 3. Sync from GitHub

#### Automatic Sync (Recommended)
1. The default GitHub URL is already configured for this project
2. Check "Create backup before sync" (recommended)
3. Click "Preview Changes" to see what files will be updated
4. Click "Sync from GitHub" to apply updates

#### Custom GitHub Repository
1. Enter a custom GitHub URL in the format:
   ```
   https://github.com/owner/repo/tree/branch/folder
   ```
   Example: `https://github.com/FirstNight1/Rokenbok-Wifi-Esp32/tree/main/RokVehicle`
2. Follow the same sync process

### 4. File Management

- **View Files**: Click "Refresh List" to see all current files with sizes
- **Download Files**: Click the 📥 button next to any file to download it
- **Delete Files**: Click the 🗑️ button (use with caution!)

### 5. Backup & Recovery

#### Create Backup
- Click "Create Backup" to save current critical files
- Backups are stored as `.bak` files and tracked in metadata

#### Restore from Backup  
- Click "Restore Backup" to revert to the last backup
- This will overwrite current files with backed-up versions

### 6. System Management

- **Restart System**: Reboots the ESP32 (you'll temporarily lose connection)
- **Memory Info**: Shows current memory usage

## Safety Features

### Automatic Backup
- Before any GitHub sync, the system can automatically backup critical files
- Backups include: `main.py`, `boot.py`, `variables/vars_store.py`, `web/web_server.py`

### File Protection
Some files are automatically protected from OTA updates:
- `variables/config.json` - Your local configuration 
- `lib/ota_backup.json` - Backup metadata
- `.bak` files - Previous backups
- System files like `.DS_Store`

### Preview Mode
- GitHub sync includes a "Preview Changes" option
- Shows exactly which files will be downloaded before applying changes
- Helps prevent accidentally overwriting important customizations

## Troubleshooting

### Common Issues

**"Failed to get GitHub file list"**
- Check that the GitHub URL is valid and accessible
- Ensure the repository and branch exist
- Verify internet connectivity on the ESP32

**"File upload failed"**  
- Check that the filename is valid (no invalid characters)
- Ensure there's enough free memory on the ESP32
- File path should not start with `/` or contain `../`

**"Backup failed"**
- Check available storage space
- Ensure the `lib/` directory exists and is writable

**Memory Issues**
- The OTA system is designed to be memory-efficient
- Large repository syncs may require multiple attempts
- Consider uploading files individually for very large projects

### Recovery Options

**If something goes wrong:**
1. Try "Restore Backup" to revert to the last known good state
2. If backup doesn't work, reconnect via USB and restore manually
3. Use the mpremote commands to upload critical files:
   ```bash
   python -m mpremote connect COM10 cp ./main.py :/main.py
   ```

**Complete recovery (worst case):**
1. Connect via USB
2. Upload a basic `main.py` and `boot.py`
3. Upload the OTA system files
4. Access web interface and restore from there

## Implementation Details

### File Structure
```
RokVehicle/
├── lib/
│   └── ota_utils.py          # Core OTA functionality
├── control/
│   └── led_status.py         # LED status manager (Pin D10)
├── web/
│   ├── web_server.py         # Updated with /ota route
│   └── pages/
│       ├── ota_page.py       # OTA web interface logic
│       └── assets/
│           └── ota_page.html # OTA web interface UI
├── variables/
│   └── vars_store.py         # Updated with OTA config
└── main.py                   # Your main application
```

### Configuration Options

In `variables/config.json`:
```json
{
  "ota_github_url": "https://github.com/FirstNight1/Rokenbok-Wifi-Esp32/tree/main/RokVehicle",
  "ota_auto_backup": true,
  "ota_last_update": null,
  "ota_update_count": 0
}
```

## Security Considerations

- **Local Network Only**: This system is designed for local network use
- **No Authentication**: The web interface doesn't include authentication
- **File Validation**: Limited validation of uploaded files
- **GitHub Access**: Uses public GitHub API (rate limits may apply)

For production deployments, consider adding:
- Authentication/authorization
- File content validation
- Encrypted communications
- Access logging
- Rate limiting

## Acknowledgments

This OTA system was inspired by:
- [Random Nerd Tutorials MicroPython OTA guide](https://randomnerdtutorials.com/esp32-esp8266-micropython-ota-updates/)
- [turfptax/ugit](https://github.com/turfptax/ugit) - MicroPython GitHub sync tool
- [raghulrajg/MicroPython-OTAUpdateManager](https://github.com/raghulrajg/MicroPython-OTAUpdateManager) - OTA update framework

The implementation combines the best aspects of these approaches while being specifically tailored for the RokVehicle project structure.