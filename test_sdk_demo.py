
from trackwise_sdk import TrackWiseClient

client = TrackWiseClient()

event = {
    "user_id": "sdk_demo_user_002",
    "event_name": "product_viewed",
    "product_id": "PROD-102",
    "properties": {
        "source": "python_sdk"
    }
}

result = client.send_event(event)

print("SDK response:")
print(result)
