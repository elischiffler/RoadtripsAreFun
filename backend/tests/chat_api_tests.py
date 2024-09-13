import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.crud.chat_crud import create_chat

client = TestClient(app)

ChatDatas = [
    {
        'chatId': 1,
        'action': None,
        'locationType': '',
        'startCoords': [],
        'startAddress': '',
        'endCoords': [],
        'endAddress': '',
        'stops': 1,
        'showInputBar': False,
        'showStopSlider': False,
        'showBudgetSlider': False,
        'showAddressInput': False,
        'workflowStarted': False,
        'startConfirmed': None,
        'endConfirmed': None,
        'initial': None,
        'route': None,
        'itinerary': None,
        'loading': False,
        'hotelBudget': None,
        'carDetails': [],
        'budget': 0,
    },
]

ChatLogs = [
    {
        'id': 1,
        'title': 'Chat 1',
        'messages': [{
            'text': 'Hello welcome to Journey Genie',
            'sender': "bot",
            'buttons': []
        }]
    }
]

@pytest.mark.asyncio
def test_add_initialized_chat():
    # Create the payload for the body (request)
    payload = {
        'ChatData': {
            'chatId': 1,
            'action': None,
            'locationType': '',
            'startCoords': [],
            'startAddress': '',
            'endCoords': [],
            'endAddress': '',
            'stops': 1,
            'showInputBar': False,
            'showStopSlider': False,
            'showBudgetSlider': False,
            'showAddressInput': False,
            'workflowStarted': False,
            'startConfirmed': None,
            'endConfirmed': None,
            'initial': None,
            'route': None,
            'itinerary': None,
            'loading': False,
            'hotelBudget': None,
            'carDetails': [],
            'budget': 0,
        },
        'ChatLog': {
            'id': 1,
            'title': 'Chat 1',
            'messages': [{
                'text': 'Hello welcome to Journey Genie',
                'sender': "bot",
                'buttons': []
            }]
        }
    }

    # Post request with correct chat_id in the path and partition_key as a query param
    response = client.post(
        '/chats/create/1?partition_key=12345678',
        json=payload
    )

    # Assert the status code is 200
    assert response.status_code == 200


def test_delete_chat():
    chat_id = 2
    # Create data
    response1 = create_chat(
        auth_token=str(88),
        chat_id=str(chat_id),
        chat_data=ChatDatas[0],
        chat_logs=ChatLogs[0],
    )
    assert response1['ResponseMetadata']['HTTPStatusCode'] == 200
    params= {
        'partition_key': 88,
        'chat_id': chat_id,
    }
    url = f'/chats/delete/{chat_id}'
    response = client.delete(
        url=url,
        params=params,
    )
    assert response.status_code == 200

if __name__ == '__main__':
    pytest.main()
