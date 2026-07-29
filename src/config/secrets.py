import json
import os


def get_google_service_account():
    return json.loads(
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    )
