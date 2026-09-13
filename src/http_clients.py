import requests


class ApiClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )

    def get(self, path: str):
        response = self.session.get(f"{self.base_url}/{path.lstrip('/')}")
        response.raise_for_status()
        return response

    def post(self, path: str, json=None):
        response = self.session.post(
            f"{self.base_url}/{path.lstrip('/')}", json=json
        )
        response.raise_for_status()
        return response
