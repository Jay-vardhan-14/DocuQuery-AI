import requests
import time

BASE_URL = "http://localhost:8000/api/v1"

USERS = {
    "admin": {"email": "admin@docuquery.ai", "password": "password123"},
    "manager": {"email": "manager@docuquery.ai", "password": "password123"},
    "employee": {"email": "employee@docuquery.ai", "password": "password123"},
}

tokens = {}

def login(role):
    res = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": USERS[role]["email"], "password": USERS[role]["password"]}
    )
    res.raise_for_status()
    tokens[role] = res.json()["access_token"]
    print(f"✅ Logged in as {role}")

def get_headers(role):
    return {"Authorization": f"Bearer {tokens[role]}"}

def upload_restricted_doc():
    content = b"Project X is a new stealth project launching in 2027. The budget is $50M. Only admins know about this."
    files = {"file": ("SuperSecretPlans.txt", content, "text/plain")}
    data = {"title": "Super Secret Plans", "access_level": "restricted"}
    res = requests.post(f"{BASE_URL}/documents/upload", headers=get_headers("admin"), files=files, data=data)
    res.raise_for_status()
    print("✅ Admin uploaded restricted document 'SuperSecretPlans.txt'")

def query(role, question):
    print(f"\n--- {role.upper()} querying: '{question}' ---")
    res = requests.post(f"{BASE_URL}/query", headers=get_headers(role), json={"query": question})
    res.raise_for_status()
    data = res.json()
    print(f"Answer: {data['answer']}")
    print("Sources:")
    for src in data['sources']:
        print(f"  - {src['document_title']} (Relevance: {src['relevance_score']:.2f})")
    return data

def verify_admin_dashboard():
    print("\n--- Testing Admin Endpoints ---")
    users_res = requests.get(f"{BASE_URL}/admin/users", headers=get_headers("admin"))
    users_res.raise_for_status()
    print(f"✅ Admin users endpoint working (found {len(users_res.json())} users)")

    metrics_res = requests.get(f"{BASE_URL}/admin/metrics", headers=get_headers("admin"))
    metrics_res.raise_for_status()
    metrics = metrics_res.json()
    print(f"✅ Admin metrics endpoint working")
    print(f"   Total Queries: {metrics['total_queries_30d']}")
    print(f"   Total Documents: {metrics['total_documents']}")

if __name__ == "__main__":
    for role in USERS:
        login(role)

    upload_restricted_doc()
    
    # Wait a second for background processing to complete
    time.sleep(2)

    # Admin should see it
    admin_data = query("admin", "What is Project X and what is the budget?")
    assert any(s["document_title"] == "Super Secret Plans" for s in admin_data["sources"]), "Admin didn't get the restricted source!"

    # Employee should NOT see it
    emp_data = query("employee", "What is Project X and what is the budget?")
    assert not any(s["document_title"] == "Super Secret Plans" for s in emp_data["sources"]), "SECURITY FLAW: Employee saw restricted source!"

    verify_admin_dashboard()
    print("\n🎉 All RBAC and Admin tests passed successfully!")
