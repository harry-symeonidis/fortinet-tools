'''
Basic FortiGate SD-WAN configuration
====================================
Written by Harry Symeonidis
Tested on FortiOS v7.2 and v7.4

USE AT YOUR OWN RISK!

This program will use your FortiGate REST API account (with super_admin privileges) to:
1) Identify your VDOMs and auto-select the (non-root) traffic VDOM if 2 (or hand you the choice if more than 2)
2) Create an Internet SD-WAN zone on your traffic VDOM.
3) Add the WAN interface of your choice to the Internet SD-WAN zone.
4) Configure a static route to your Internet SD-WAN zone.

Set the API_KEY environment variable to your REST API admin key. For example in PowerShell:
[System.Environment]::SetEnvironmentVariable("API_KEY","trnbrw313czxhG5y1hHnGHkcHpN1nm")
'''

# Import necessary libraries
import os
import requests
import ipaddress
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Function to validate IPv4 address


def validateIpv4(ip):
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ipaddress.AddressValueError:
        return False


def getUserInput():
    # First get the management IPv4 address
    while True:
        management_ip = input(
            "Please enter the FortiGate management IPv4 address: ")
        if validateIpv4(management_ip):
            break
        else:
            print("Invalid IP address. Please enter a valid IPv4 address.")

    # Define the base URL for the API
    base_url = f"https://{management_ip}/api/v2"

    # Then confirm the WAN interface name
    wan_interface_name = input("Enter the primary WAN name: ")

    # And finally get the Internet router IPv4 address
    while True:
        internet_gateway_ip = input(
            "Enter the Internet gateway IPv4 address: ")
        if validateIpv4(internet_gateway_ip):
            break
        else:
            print("Invalid IP address. Please enter a valid IPv4 address.")

    return base_url, wan_interface_name, internet_gateway_ip


# Get the API key from the environment
api_key = os.getenv("API_KEY")

# Define the headers for API requests
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

# Function to get the correct traffic VDOM name


def getTrafficVdomName(base_url, headers):
    # Send the API request to get all the configured VDOMs
    response = requests.get(
        f"{base_url}/cmdb/system/vdom", headers=headers, verify=False)

    # Check the response
    if response.status_code == 200:
        vdoms = response.json()['results']
        if len(vdoms) == 2:
            # If it's only "root" and another one, get the second
            vdom = vdoms[1]['name']
            print(f"The VDOM is set to {vdom}")
        elif len(vdoms) > 2:
            # If it's "root" and 2 or more others, then display a menu to confirm the correct VDOM
            print("Please select the correct VDOM:")
            for i, vdom in enumerate(vdoms):
                print(f"{i+1}. {vdom['name']}")
            vdom_number = int(input("Enter the number of the VDOM: "))
            vdom = vdoms[vdom_number-1]['name']
            print(f"The VDOM is set to {vdom}")
    else:
        print(f"Failed to get the VDOMs. Status code: {response.status_code}")

    return vdom

# Function to create the Internet SD-WAN zone


def createInternetSdwanZone(base_url, headers, vdom):
    zone_data = {
        "zone": [{"name": "Internet SD-WAN"}]
    }
    response = requests.put(f"{base_url}/cmdb/system/sdwan?vdom={vdom}",
                            headers=headers, json=zone_data, verify=False)
    if response.status_code == 200:
        print("Internet SD-WAN zone created successfully.")

    else:
        print(
            f"Failed to create Internet SD-WAN zone. Status code: {response.status_code}")

# Function to add the WAN interface to the Internet SD-WAN zone


def addInterfaceToSdwanZone(base_url, headers, vdom, wan_interface_name, internet_gateway_ip):
    interface_data = {
        "members": [{"interface": wan_interface_name,
                    "zone": "Internet SD-WAN",
                     "gateway": internet_gateway_ip}]
    }
    response = requests.put(f"{base_url}/cmdb/system/sdwan?vdom={vdom}",
                            headers=headers, json=interface_data, verify=False)
    if response.status_code == 200:
        print(
            f"{wan_interface_name} interface added to the Internet SD-WAN zone successfully.")
    else:
        print(f"Failed to add {
              wan_interface_name} interface to the Internet SD-WAN zone. Status code: {response.status_code}")

# Function to configure the default static route to the Internet SD-WAN zone


def configureDefaultRoute(base_url, headers, vdom):
    response = requests.get(
        f"{base_url}/cmdb/router/static?vdom={vdom}", headers=headers, verify=False)
    if response.status_code == 200:
        routes = response.json()['results']
        default_route = next(
            (route for route in routes if route['dst'] == "0.0.0.0 0.0.0.0"), None)
        if default_route:
            # If a default route exists, delete it
            response = requests.delete(f"{base_url}/cmdb/router/static/{
                default_route['seq_num']}?vdom={vdom}", headers=headers, verify=False)
            if response.status_code == 200:
                print("Default route deleted successfully.")
            else:
                print(f"Failed to delete default route. Status code: {
                    response.status_code}")
        else:
            # If no default route exists, create it
            route_data = {
                "dst": "0.0.0.0 0.0.0.0",
                "comment": "Default static route created programmatically.",
                "sdwan-zone": [{"name": "Internet SD-WAN"}]
            }
            response = requests.post(
                f"{base_url}/cmdb/router/static?vdom={vdom}", headers=headers, json=route_data, verify=False)
            if response.status_code == 200:
                print("Default route set on the Internet SD-WAN zone successfully.")
            else:
                print(
                    f"Failed to set default route on the Internet SD-WAN zone. Status code: {response.status_code}")
    else:
        print(f"Failed to get the static routes. Status code: {
            response.status_code}")


def main():
    # Get initial user input
    base_url, wan_interface_name, internet_gateway_ip = getUserInput()
    # Get the traffic VDOM name
    vdom = getTrafficVdomName(base_url, headers)
    # Create the Internet SD-WAN zone
    createInternetSdwanZone(base_url, headers, vdom)
    # Add the WAN interface to the Internet SD-WAN zone
    addInterfaceToSdwanZone(base_url, headers, vdom,
                            wan_interface_name, internet_gateway_ip)
    # Configure the default static route
    configureDefaultRoute(base_url, headers, vdom)


if __name__ == "__main__":
    main()
