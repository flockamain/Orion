import requests
import urllib3
import getpass
from orionsdk import SwisClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PRTG_SERVER = 'xxxx'    # e.g., https://prtg.company.net
ORION_SERVER = 'xxxx'   # e.g., your-orion-server.company.net

# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────

def get_credentials():
    print("Enter credentials for both platforms.")

    print("\nPRTG Login")
    prtg_user = input("PRTG Username: ").strip()
    prtg_pass = getpass.getpass("PRTG Password: ")

    print("\nSolarWinds Orion Login")
    orion_user = input("Orion Username: ").strip()
    orion_pass = getpass.getpass("Orion Password: ")

    return prtg_user, prtg_pass, orion_user, orion_pass

def test_prtg_login(username, password):
    url = f"{PRTG_SERVER}/api/table.json"
    params = {'username': username, 'password': password}
    try:
        response = requests.get(url, params=params, verify=False)
        response.raise_for_status()
        data = response.json()
        print(f"  ✓ PRTG connected | Version: {data.get('prtg-version')} | Total Devices: {data.get('treesize')}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ✗ PRTG connection failed: {e}")
        return False

def test_orion_login(username, password):
    try:
        swis = SwisClient(ORION_SERVER, username, password, verify=False)
        result = swis.query("SELECT COUNT(*) AS NodeCount FROM Orion.Nodes")
        node_count = result['results'][0]['NodeCount']
        print(f"  ✓ Orion connected | Total Nodes: {node_count}")
        return swis
    except Exception as e:
        print(f"  ✗ Orion connection failed: {e}")
        return None

# ─────────────────────────────────────────────
# PRTG
# ─────────────────────────────────────────────

def get_all_prtg_devices(username, password):
    url = f"{PRTG_SERVER}/api/table.json"
    all_devices = []
    start = 0

    while True:
        params = {
            'content': 'devices',
            'output': 'json',
            'columns': 'objid,device',
            'username': username,
            'password': password,
            'count': 2500,
            'start': start
        }
        response = requests.get(url, params=params, verify=False)
        response.raise_for_status()
        data = response.json()
        devices = data.get('devices', [])
        all_devices.extend(devices)
        if len(all_devices) >= data.get('treesize', 0):
            break
        start += 2500

    return all_devices

def search_prtg(username, password, search_term):
    devices = get_all_prtg_devices(username, password)
    matches = [d for d in devices if search_term in d['device'].lower()]
    return matches

def delete_prtg_device(username, password, objid, device_name):
    url = f"{PRTG_SERVER}/api/deleteobject.htm"
    params = {
        'id': objid,
        'approve': 1,
        'username': username,
        'password': password
    }
    try:
        response = requests.get(url, params=params, verify=False)
        response.raise_for_status()
        print(f"  ✓ Successfully deleted from PRTG: {device_name} (ID: {objid})")
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Failed to delete from PRTG: {e}")

# ─────────────────────────────────────────────
# ORION
# ─────────────────────────────────────────────

def search_orion(swis, search_term):
    result = swis.query(
        "SELECT NodeID, Caption, IPAddress, Status FROM Orion.Nodes WHERE Caption LIKE @name",
        name=f"%{search_term}%"
    )
    return result['results']

def delete_orion_node(swis, node_id, node_name):
    node_uri = f"swis://orion/Orion/Orion.Nodes/NodeID={node_id}"
    try:
        swis.delete(node_uri)
        print(f"  ✓ Successfully deleted from Orion: {node_name} (NodeID: {node_id})")
    except Exception as e:
        print(f"  ✗ Failed to delete from Orion: {e}")

# ─────────────────────────────────────────────
# COMBINED SEARCH & DELETE
# ─────────────────────────────────────────────

def confirm_delete(label):
    confirm = input(f"\nType 'YES I WANT TO DELETE THIS SINGLE NODE' to confirm deletion from {label}: ").strip()
    return confirm == "YES I WANT TO DELETE THIS SINGLE NODE"

def search_and_delete(prtg_user, prtg_pass, swis):
    search_term = input("\nEnter the string to search for across both platforms: ").strip().lower()
    if not search_term:
        print("No search term provided. Exiting.")
        return

    # Search both platforms simultaneously
    print(f"\nSearching both platforms for '{search_term}'...")
    prtg_matches = search_prtg(prtg_user, prtg_pass, search_term)
    orion_matches = search_orion(swis, search_term)

    # ── Print results ──────────────────────────────
    print(f"\n{'─'*40}")
    print(f"PRTG   — {len(prtg_matches)} match(es) found:")
    for d in prtg_matches:
        print(f"  - {d['device']} (ID: {d['objid']})")

    print(f"\nOrion  — {len(orion_matches)} match(es) found:")
    for n in orion_matches:
        print(f"  - {n['Caption']} (NodeID: {n['NodeID']}, IP: {n['IPAddress']})")
    print(f"{'─'*40}")

    # ── Determine what's deletable (single match only) ──
    prtg_deletable  = len(prtg_matches) == 1
    orion_deletable = len(orion_matches) == 1
    prtg_blocked    = len(prtg_matches) > 1
    orion_blocked   = len(orion_matches) > 1

    if prtg_blocked:
        print("\nPRTG: Multiple matches found — refine your search to a single result before deleting.")
    if orion_blocked:
        print("\nOrion: Multiple matches found — refine your search to a single result before deleting.")

    # ── Nothing to delete ──────────────────────────
    if not prtg_deletable and not orion_deletable:
        print("\nNo single-match results to delete on either platform.")
        return

    # ── Ask what to delete ─────────────────────────
    print("\nWhat would you like to delete?")
    if prtg_deletable and orion_deletable:
        print("  1. Delete from both PRTG and Orion")
        print("  2. Delete from PRTG only")
        print("  3. Delete from Orion only")
        print("  4. Cancel")
        choice = input("Enter 1, 2, 3 or 4: ").strip()
    elif prtg_deletable and not orion_deletable:
        print("  (Orion: no single match found — only PRTG deletion available)")
        print("  1. Delete from PRTG")
        print("  2. Cancel")
        choice = input("Enter 1 or 2: ").strip()
        choice = '2' if choice == '2' else 'prtg_only'
    elif orion_deletable and not prtg_deletable:
        print("  (PRTG: no single match found — only Orion deletion available)")
        print("  1. Delete from Orion")
        print("  2. Cancel")
        choice = input("Enter 1 or 2: ").strip()
        choice = '2' if choice == '2' else 'orion_only'

    # ── Execute deletions with confirmation ────────
    if choice in ('1', '2') and prtg_deletable and orion_deletable:
        # Both available, choice 1 = both, choice 2 = prtg only
        if choice == '1':
            if confirm_delete("PRTG and Orion"):
                delete_prtg_device(prtg_user, prtg_pass, prtg_matches[0]['objid'], prtg_matches[0]['device'])
                delete_orion_node(swis, orion_matches[0]['NodeID'], orion_matches[0]['Caption'])
        elif choice == '2':
            if confirm_delete("PRTG"):
                delete_prtg_device(prtg_user, prtg_pass, prtg_matches[0]['objid'], prtg_matches[0]['device'])

    elif choice == '3' and prtg_deletable and orion_deletable:
        if confirm_delete("Orion"):
            delete_orion_node(swis, orion_matches[0]['NodeID'], orion_matches[0]['Caption'])

    elif choice == 'prtg_only':
        if confirm_delete("PRTG"):
            delete_prtg_device(prtg_user, prtg_pass, prtg_matches[0]['objid'], prtg_matches[0]['device'])

    elif choice == 'orion_only':
        if confirm_delete("Orion"):
            delete_orion_node(swis, orion_matches[0]['NodeID'], orion_matches[0]['Caption'])

    else:
        print("Delete cancelled.")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == '__main__':
    prtg_user, prtg_pass, orion_user, orion_pass = get_credentials()

    print("\nConnecting to both platforms...")
    prtg_ok = test_prtg_login(prtg_user, prtg_pass)
    swis    = test_orion_login(orion_user, orion_pass)

    if not prtg_ok and not swis:
        print("\nFailed to connect to both platforms. Exiting.")
    elif not prtg_ok:
        print("\nWarning: PRTG unavailable. Continuing with Orion only.")
        search_and_delete(None, None, swis)
    elif not swis:
        print("\nWarning: Orion unavailable. Continuing with PRTG only.")
        search_and_delete(prtg_user, prtg_pass, None)
    else:
        search_and_delete(prtg_user, prtg_pass, swis)
