# OTA Update Instructions

# THIS FUNCTIONALITY IS NOT CURRENTLY WORKING!

This guide will walk you through downloading the latest Rokenbok WiFi ESP32 project from GitHub and applying updates to your vehicles or FPV systems using the Over-The-Air (OTA) update system.

## What You'll Need

- A computer with internet access and a web browser
- Your Rokenbok WiFi-enabled vehicle or FPV system connected to your local WiFi network or running in AP mode
- Basic knowledge of downloading and extracting ZIP files

## Step 1: Download the Latest Project Files from GitHub

### 1.1 Access the GitHub Repository
1. Open your web browser and navigate to: `https://github.com/FirstNight1/Rokenbok-Wifi-Esp32`
2. You should see the main project page with folders like `RokCommon`, `RokVehicle`, and `RokVision`

### 1.2 Download the Project
1. Look for the green **"Code"** button (usually near the top right of the file listing)
2. Click the **"Code"** button
3. Select **"Download ZIP"** from the dropdown menu
4. Save the ZIP file to your computer (typically in your Downloads folder)
5. The file will be named something like `Rokenbok-Wifi-Esp32-main.zip`

### 1.3 Extract the Project Files
1. Locate the downloaded ZIP file on your computer
2. Right-click on the ZIP file and select **"Extract All..."** (Windows) or double-click (Mac)
3. Choose a location to extract the files (your Desktop or Documents folder works well)
4. After extraction, you should see a folder named `Rokenbok-Wifi-Esp32-main` containing:
   - `RokCommon` folder
   - `RokVehicle` folder  
   - `RokVision` folder
   - Other files and documentation

## Step 2: Access Your Device's Web Interface

### 2.1 Find Your Device
1. Make sure your Rokenbok WiFi device (vehicle or FPV system) is powered on and connected to your WiFi network or in AP mode
2. Look for the device's IP address:
   - **Option A**: Check your router's admin panel for connected devices
   - **Option B**: Use your computer's network discovery to find "RokVehicle" or "RokVision" devices
   - **Option C**: If the device is in AP mode, connect to its WiFi network (name usually starts with "RokVehicle" or "RokVision")

### 2.2 Open the Web Interface
1. Open your web browser
2. Enter the device's IP address in the address bar (example: `http://192.168.1.100`.  Typically `http://192.168.4.1` if in AP mode.)
3. You should see the device's main control page

## Step 3: Navigate to the OTA Update Page

1. Look for a navigation menu or link to **"Update"** or **"System Updates"**
2. Click on the Updates link
3. You should now see the OTA Update page with a 4-step process

## Step 4: Upload Project Files

### 4.1 Upload RokCommon (Required for All Devices)
1. In **Step 1: Upload Folders**, find the **"Upload RokCommon"** section
2. Click **"Choose Files"** or the folder selection button
3. Navigate to your extracted project folder
4. Select the **entire `RokCommon` folder** (make sure you're selecting the folder, not individual files)
5. Click **"Upload RokCommon"**
6. Wait for the upload to complete - you should see a success message

### 4.2 Upload Device-Specific Folder
1. In the **"Upload Device Folder"** section:
   - **For Vehicles**: Select "RokVehicle" from the dropdown, then upload the `RokVehicle` folder
   - **For FPV Systems**: Select "RokVision" from the dropdown, then upload the `RokVision` folder
2. Click **"Choose Files"** or the folder selection button
3. Select the appropriate folder (`RokVehicle` or `RokVision`)
4. Click **"Upload Device Folder"**
5. Wait for the upload to complete

### 4.3 Validate Uploads
1. Click **"Validate Uploads"** to check that both folders were uploaded correctly
2. You should see a green status message indicating successful validation
3. The upload status section should show both folders with file counts and upload timestamps

## Step 5: Preview Changes

1. Once uploads are validated, **Step 2: Preview Changes** will become available
2. Click **"Preview Changes"** to see what files will be updated
3. Review the list of:
   - **New files**: Files that will be added
   - **Updated files**: Files that will be modified
   - **Current files**: Existing files on the device

## Step 6: Create a Backup (Recommended)

1. **Step 3: Create Backup** is available anytime
2. Enter a description for your backup (example: "Before January 2026 update")
3. Click **"Create Backup"**
4. Wait for the backup process to complete
5. **Important**: This backup can be used to restore your device if something goes wrong

## Step 7: Apply Updates

1. **Step 4: Apply Updates** will be available after creating a backup
2. Choose your options:
   - **Delete existing files**: ✅ Recommended for clean updates
   - **Preserve config files**: ✅ Keep your WiFi and device settings
3. Click **"Apply Updates"**
4. Wait for the update process to complete
5. You should see a success message when finished

## Step 8: Restart Your Device

1. In **System Actions**, click **"Restart System"**
2. Confirm the restart when prompted
3. Wait about 30-60 seconds for your device to fully restart
4. The device should reconnect to your WiFi network automatically

## Step 9: Verify the Update

1. After the device restarts, access the web interface again
2. Check that the device is functioning normally
3. Test vehicle controls or FPV functionality to ensure everything works properly

## Troubleshooting

### Upload Issues
- **"No files found in upload"**: Make sure you're selecting entire folders, not individual files
- **"Invalid folder type"**: Ensure you're uploading `RokCommon`, `RokVehicle`, or `RokVision` folders specifically
- **Upload timeout**: Large uploads may take several minutes; be patient

### Connection Issues  
- **Can't access web interface**: Verify the device is powered on and connected to WiFi
- **Page won't load**: Try refreshing the browser or checking the IP address
- **WiFi connection lost**: The device may have switched to AP mode; look for its WiFi network

### Update Issues
- **Update failed**: Use the **"Restore from Backup"** option to return to the previous version
- **Device won't restart**: Power cycle the device manually by turning it off and on
- **Configuration lost**: Re-enter WiFi settings and device configuration if needed

## Safety Notes

- Always create a backup before applying updates
- Don't power off the device during the update process
- Keep the original project files in case you need to repeat the process
- If updates fail, you can always restore from backup or re-flash the device firmware

## Getting Help

If you encounter issues not covered in this guide:
1. Check the main project README.md for additional troubleshooting
2. Review the device's error messages carefully
3. Try the backup/restore process if updates fail
4. As a last resort, you may need to re-flash the MicroPython firmware and start over

---

**Remember**: This process updates the software on your device but doesn't change your WiFi settings, device name, or other configuration - those are preserved during updates.