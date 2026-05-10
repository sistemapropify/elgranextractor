import requests

# Probar el endpoint de flujos
url = "http://127.0.0.1:8000/api/v1/intelligence/chat-workflows/"

try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")