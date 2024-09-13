import boto3
from decimal import Decimal

session = boto3.Session(profile_name='AdministratorAccess-654654195586')
dynamodb = session.resource('dynamodb', region_name='us-west-1')

table = dynamodb.Table('RoadtripAI')

def create_chat_log(userId, chatId, chatData):
    response = table.put_item(
        Item={
            'UserId': userId,
            'ChatId': chatId,
            'chatData': chatData
        }
    )
    return response

create_chat_log('123456678', '1', {'route': 5, 'action': 'testing', 'coords': [[5324,Decimal(str(.1234))], [141123,31413]]})