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
        'startAddress': ['', '', '', ''],
        'endCoords': [],
        'endAddress': ['', '', '', ''],
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
    },{
            'chatId': 2,
            'action': 'Hello World',
            'locationType': '',
            'startCoords': [],
            'startAddress': '',
            'endCoords': [],
            'endAddress': '',
            'stops': 1,
            'showInputBar': True,
            'showStopSlider': False,
            'showBudgetSlider': False,
            'showAddressInput': True,
            'workflowStarted': True,
            'startConfirmed': [124.324, 52134],
            'endConfirmed': [-112.0234, 48.57689],
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

# @pytest.mark.asyncio
def test_add_initialized_chat():
    # Create the payload for the body (request)
    payload = {
        'PartitionKey': '12345678',
        'ChatData': ChatDatas[0],
        'ChatLog': ChatLogs[0]
    }

    # Post request with correct chat_id in the path and partition_key as a query param
    response = client.post(
        '/chats/create/1',
        json=payload
    )
    print(response.json())

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


def test_update_chat():
    chat_id = 3
    partition_key = 88
    response1 = create_chat(
        auth_token=str(partition_key),
        chat_id=str(chat_id),
        chat_data=ChatDatas[0],
        chat_logs=ChatLogs[0],
    )
    assert response1['ResponseMetadata']['HTTPStatusCode'] == 200
    payload = {
        'PartitionKey': '88',
        'ChatData': {
            'chatId': 1,
            'action': 'Address',
            'locationType': '',
            'startCoords': [],
            'startAddress': ['','','',''],
            'endCoords': [],
            'endAddress': ['','','',''],
            'stops': 1,
            'showInputBar': True,
            'showStopSlider': False,
            'showBudgetSlider': True,
            'showAddressInput': False,
            'workflowStarted': False,
            'startConfirmed': None,
            'endConfirmed': [116.12341324123412,15.234234234],
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
            },
                {
                    'text': 'I want to drive cross country fro LA to NYC',
                    'sender': "user",
                    'buttons': []
                }]
        }
    }

    # Post request with correct chat_id in the path and partition_key as a query param
    response = client.put(
        f'/chats/update/{chat_id}?partition_key={partition_key}',
        json=payload
    )
    print(response.json())
    assert response.status_code == 200

def test_initialize_chats():
    partition_key = 88
    print(partition_key, ChatDatas[0], ChatLogs[0])
    response = create_chat(
        auth_token=str(partition_key),
        chat_id=str(1),
        chat_data=ChatDatas[0],
        chat_logs=ChatLogs[0],
    )
    assert response['ResponseMetadata']['HTTPStatusCode'] == 200
    response = create_chat(
        auth_token=str(partition_key),
        chat_id=str(2),
        chat_data=ChatDatas[0],
        chat_logs=ChatLogs[0],
    )
    assert response['ResponseMetadata']['HTTPStatusCode'] == 200
    response = create_chat(
        auth_token=str(partition_key),
        chat_id=str(3),
        chat_data=ChatDatas[0],
        chat_logs=ChatLogs[0],
    )
    assert response['ResponseMetadata']['HTTPStatusCode'] == 200
    params = {
        'partition_key': partition_key,
    }
    response = client.get('/chats', params=params)
    assert response.status_code == 200
    data = response.json()
    print(data)
    assert len(data) == 3




if __name__ == '__main__':
    pytest.main(["-k", "test_initialize_chats"])
