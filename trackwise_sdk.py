
import requests


class TrackWiseClient:
    def __init__(self, base_url="http://127.0.0.1:5000"):
        self.base_url = base_url.rstrip("/")

    def send_event(self, event_data):
        url = f"{self.base_url}/api/events"

        try:
            response = requests.post(
                url,
                json=event_data,
                timeout=10
            )

            try:
                response_data = response.json()
            except ValueError:
                response_data = {"message": response.text}

            return {
                "success": response.ok,
                "status_code": response.status_code,
                "data": response_data
            }

        except requests.RequestException as error:
            return {
                "success": False,
                "status_code": None,
                "error": str(error)
            }

