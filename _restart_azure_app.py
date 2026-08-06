"""Azure App Service Restart via MSAL Device Code Flow."""
import msal
import requests
import sys
import json

TENANT_ID = "f8cdef31-a31e-4b4a-93e4-5f571e91255a"
CLIENT_ID = "aebc6443-996d-45c2-90f0-388ff96faa56"

app = msal.PublicClientApplication(
    CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}"
)

accounts = app.get_accounts()
if accounts:
    result = app.acquire_token_silent(
        ["https://management.azure.com/.default"],
        account=accounts[0]
    )
    if "access_token" in result:
        print("TOKEN_OK")
        token = result["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        subs = requests.get(
            "https://management.azure.com/subscriptions?api-version=2020-01-01",
            headers=headers
        ).json()
        
        for sub in subs.get("value", []):
            sid = sub["subscriptionId"]
            sites = requests.get(
                f"https://management.azure.com/subscriptions/{sid}/providers/Microsoft.Web/sites?api-version=2022-09-01",
                headers=headers
            ).json()
            for site in sites.get("value", []):
                if "granextractor" in site["name"].lower():
                    rg = site["id"].split("/resourceGroups/")[1].split("/")[0]
                    print(f"Encontrado: {site['name']} en RG: {rg}")
                    r = requests.post(
                        f"https://management.azure.com/subscriptions/{sid}/resourceGroups/{rg}/providers/Microsoft.Web/sites/{site['name']}/restart?api-version=2022-09-01",
                        headers=headers
                    )
                    print(f"REINICIO: status {r.status_code}")
                    sys.exit(0)
        print("No se encontro el App Service")
        sys.exit(0)

# Device code flow
print("DEVICE_CODE")
flow = app.initiate_device_flow(scopes=["https://management.azure.com/.default"])
print(f"URL: {flow['verification_uri']}")
print(f"CODE: {flow['user_code']}")
sys.stdout.flush()

result = app.acquire_token_by_device_flow(flow, timeout=120)
if "access_token" in result:
    print("TOKEN_OK")
    token = result["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    subs = requests.get(
        "https://management.azure.com/subscriptions?api-version=2020-01-01",
        headers=headers
    ).json()
    
    for sub in subs.get("value", []):
        sid = sub["subscriptionId"]
        sites = requests.get(
            f"https://management.azure.com/subscriptions/{sid}/providers/Microsoft.Web/sites?api-version=2022-09-01",
            headers=headers
        ).json()
        for site in sites.get("value", []):
            if "granextractor" in site["name"].lower():
                rg = site["id"].split("/resourceGroups/")[1].split("/")[0]
                print(f"Encontrado: {site['name']} en RG: {rg}")
                r = requests.post(
                    f"https://management.azure.com/subscriptions/{sid}/resourceGroups/{rg}/providers/Microsoft.Web/sites/{site['name']}/restart?api-version=2022-09-01",
                    headers=headers
                )
                print(f"REINICIO: status {r.status_code}")
                sys.exit(0)
    print("No se encontro")
else:
    print(f"ERROR: {result.get('error_description', 'desconocido')}")
