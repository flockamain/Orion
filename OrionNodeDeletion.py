from orionsdk import SwisClient
import requests
import urllib3
import getpass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ORION_SERVER = 'xxxx'  # e.g., your-orion-server.company.net

def get_credentials():
    # Prompt for username and password
    print("SolarWinds Orion Login")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    return username, password

# Initial login - test connection and print some info about the Orion instance
def test_orion_login(username, password):
    try:
        swis = SwisClient(ORION_SERVER, username, password, verify=False)
        # Query basic instance info to verify connection
        result = swis.query("SELECT COUNT(*) AS NodeCount FROM Orion.Nodes")
        node_count = result['results'][0]['NodeCount']
        print("Successfully connected to SolarWinds Orion!")
        print(f"Logged in as: {username}")
        print(f"Total Nodes: {node_count}")
        return swis
    except Exception as e:
        print("Failed to connect to SolarWinds Orion:")
        print(e)
        return None

# Delete a node by its NodeID, only on exact confirmation and only if
# exactly one match was found in the search, to prevent deleting the wrong node.
def delete_node(swis, node_uri, node_name, node_id):
    # Only allow delete if exactly one match was found
    confirm = input(f"\nYou are about to delete: {node_name} (NodeID: {node_id})\nType 'YES I WANT TO DELETE THIS SINGLE NODE' to confirm: ").strip()

    # Confirmation must match exactly to proceed with deletion
    if confirm != "YES I WANT TO DELETE THIS SINGLE NODE":
        print("Confirmation did not match. Delete cancelled.")
        return

    try:
        swis.delete(node_uri)
        print(f"Successfully deleted: {node_name} (NodeID: {node_id})")
    # If deletion doesn't work, print error message with details
    except Exception as e:
        print(f"Failed to delete node:")
        print(e)

# Search function to look for nodes by name using a LIKE search.
# Not case sensitive, and will return all nodes whose Caption contains the search term.
def search_nodes(swis):
    search_term = input("Enter the string to search for in node names: ").strip()
    if not search_term:
        print("No search term provided. Exiting.")
        return

    result = swis.query(
        "SELECT NodeID, Caption, IPAddress, Status FROM Orion.Nodes WHERE Caption LIKE @name",
        name=f"%{search_term}%"
    )

    matches = result['results']

    if matches:
        print(f"\nFound {len(matches)} node(s) containing '{search_term}':")
        for node in matches:
            print(f"  - {node['Caption']} (NodeID: {node['NodeID']}, IP: {node['IPAddress']})")

        # Only offer delete if exactly one node was found
        if len(matches) == 1:
            node = matches[0]
            delete_choice = input(f"\nWould you like to delete '{node['Caption']}'? (yes/no): ").strip().lower()
            if delete_choice == 'yes':
                # Build the node's URI for the delete call
                node_uri = f"swis://orion/Orion/Orion.Nodes/NodeID={node['NodeID']}"
                delete_node(swis, node_uri, node['Caption'], node['NodeID'])
            else:
                print("Delete skipped.")
        else:
            print("\nMultiple nodes found — refine your search to a single result before deleting.")
    else:
        print(f"No nodes found containing '{search_term}'.")

# Run the script
if __name__ == '__main__':
    username, password = get_credentials()
    swis = test_orion_login(username, password)
    if swis:
        search_nodes(swis)
