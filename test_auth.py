import requests

try:
    res = requests.post("http://localhost:8000/api/auth/login", json={"login": "prokuror", "password": "prokuror123"})
    if res.status_code == 200:
        token = res.json().get("access_token")
        stats = requests.get("http://localhost:8000/api/persons/assignments/stats/remaining-days?max_days=5", headers={"Authorization": f"Bearer {token}"})
        print(stats.status_code)
        print(stats.json())
    else:
        print("Login failed:", res.status_code, res.text)
except Exception as e:
    print("Error:", e)
