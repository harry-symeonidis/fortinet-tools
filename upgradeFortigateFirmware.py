# *****************************************************************************#
# DISCLAIMER: Use at your own risk!                                            #
# Upgrading wrong firmware might cause configuration loss or other damage!     #
# **************************************************************************** #
# This Python 3 program will connect to all FortiGate firewalls in a given CSV #
# file and upgrade their firmware with a local FortiOS image file.             #
# **************************************************************************** #
# The CSV file must have 3 fields with these exact names:                      #
# fgt_name,fw_ip,api_token                                                     #
# *****************************************************************************#

import requests
import urllib3
import os
import csv
import base64
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_available_firmware(fw_ip, api_token):
    # Retrieve the current firmware version and available firmware versions from the FortiGate API
    url = f"https://{fw_ip}/api/v2/monitor/system/firmware"
    headers = {"Authorization": "Bearer {}".format(api_token)}
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code != 200:
        print(f"Error: unable to retrieve firmware versions from FortiGate API for firewall at {fw_ip}")
        return None, None
    firmware_json = response.json()
    current_firmware = firmware_json["results"]["current"]["version"]
    available_firmware = []
    for fw in firmware_json["results"]["available"]:
        version = fw.get("version")
        build = fw.get("build")
        releaseType = fw.get("release-type")
        maturity = fw.get("maturity")
        notes = fw.get("notes")
        if version and build and releaseType and maturity:
            firmware_dict = {"version": version, "build": build, "release-type": releaseType, "maturity": maturity, "notes": notes}
            available_firmware.append(firmware_dict)
    return current_firmware, available_firmware   

def print_firmware_options(current_firmware, available_firmware):
    # Print a numbered list of available firmware versions
    print("Firmware Versions:\n")
    print(f"0. Current Version: {current_firmware}")
    for i, fw in enumerate(available_firmware):
        print(f"{i+1}. Version: {fw['version']}, Build: {fw['build']}, Release Type: {fw['release-type']}, Maturity: {fw['maturity']}")

def display_firmware():
    current_firmware, available_firmware = get_available_firmware()
    print_firmware_options(current_firmware, available_firmware)

def upload_firmware(fw_ip, api_token, filename):
    # Upload the firmware image to the FortiGate device
    url = f"https://{fw_ip}/api/v2/monitor/system/firmware/upgrade"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    data = {
        "source": "upload",
        "file_content": base64.b64encode(open(filename, "rb").read()).decode(),
        "filename": os.path.basename(filename)
    }
    response = requests.post(url, headers=headers, json=data, verify=False)
    if response.status_code != 200:
        print(f"Error: unable to upload firmware image to FortiGate device at {fw_ip}")
        return None
    response_json = response.json()
    return response_json.get("file_id")

def parse_version_from_filename(filename):
    # Extract the version number from the filename using regex
    pattern = r"v?(\d+\.\d+\.\d+)"
    match = re.search(pattern, filename)
    if match:
        # Add the 'v' character to the beginning of the version number
        version = "v" + match.group(1)
        return version
    else:
        return None

def save_configuration(fgt_name, fw_ip, api_token):
    # Retrieve the configuration file from the FortiGate device and save it to a local file
    url = f"https://{fw_ip}/api/v2/monitor/system/config/backup"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    data = {
        "destination": "file",
        "scope": "global",
    }
    response = response = requests.post(url, headers=headers, json=data, verify=False)
    if response.status_code != 200:
        print(f"Error: unable to retrieve configuration file from FortiGate {fgt_name} at {fw_ip}")
        return None
    filename = f"{fgt_name}-{fw_ip}-config-backup.conf"
    with open(filename, "w") as f:
        f.write(response.text)
    print(f"Configuration file saved to {filename}")

def main():
    print("FortiGate firewall firmware upgrade script\n")
    filename = input("Enter the filename of the firmware image to upgrade to: ")
    version = parse_version_from_filename(filename)
    if not version:
        print("Error: Unable to extract firmware version from filename.")
        exit(1)

    # Read the firewall IP and API token from the CSV file
    with open('firewalls.csv', 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            fgt_name = row['fgt_name']
            fw_ip = row['fw_ip']
            api_token = row['api_token']
            if not (fgt_name and fw_ip and api_token):
                print(f"Error: Missing information for firewall '{fgt_name}' in firewalls.csv")
                continue
            
            # Check if the current firewall is the one we want to upgrade
            print(f"\nConnecting to {fgt_name} ({fw_ip})...\n")
            try:
                current_firmware, available_firmware = get_available_firmware(fw_ip, api_token)
            except Exception as e:
                print(f"Error: Unable to connect to {fgt_name} ({fw_ip}). Exception: {e}")
                continue
            
            print_firmware_options(current_firmware, available_firmware)
            version_found = False
            for fw in available_firmware:
                if fw['version'] == version:
                    version_found = True
                    break
            
            if version_found:
                # Save current global configuration                                
                save_configuration(fgt_name, fw_ip, api_token)
                
                print(f"\nFirmware upgrade started for {fgt_name}. Filename: {filename}")
                
                # Upgrade firmware using the given filename
                try:
                    file_id = upload_firmware(fw_ip, api_token, filename)
                except Exception as e:
                    print(f"Error: Unable to upgrade firmware on {fgt_name} ({fw_ip}). Exception: {e}")
                    continue
                
                print(f"Firmware upgrade completed for {fgt_name}.\n")
            else:
                print(f"Error: Firmware version {version} not found for {fgt_name}.\n")

if __name__ == '__main__':
    main()
