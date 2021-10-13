import boto3
from logging import get_logger
import os
import json
from datetime import date, timedelta,datetime
from slack import WebClient
from slack.errors import SlackApiError
import re


logger = get_logger("aws_health")
client = boto3.client('health')
mode = os.environ.get("MODE","issues")
end_date = (date.today() + timedelta(days=7)).isoformat()
start_date = (date.today()).isoformat()
oldest_message_date = datetime.fromisoformat((date.today()- timedelta(hours=24)).isoformat()).timestamp()
env = os.environ.get("env")

slack_token = os.environ.get("SLACK_TOKEN")
slack_channel = '#CHANNEL'
slack_channel_id = 'BLA BLA BLA'
slack_icon_emoji = ':see_no_evil:'
slack_user_name = 'AWS Monitor'
slack_client = WebClient(token=slack_token)

def post_message_to_slack(blocks):
    try:
        response = slack_client.chat_postMessage(
            channel=slack_channel,
            blocks=json.dumps(blocks,sort_keys=True)
        )
    except SlackApiError as e:
        # You will get a SlackApiError if "ok" is False
        assert e.response["error"]

def check_old_messages(blocks_to_check):
    # Store conversation history
    conversation_history = []
    # ID of the channel you want to send the message to
    channel_id = slack_channel_id
    try:
        result = slack_client.conversations_history(channel=channel_id,oldest=oldest_message_date)
        conversation_history = result["messages"]
        messages_to_check = []
        for message in conversation_history:
            if 'blocks' in message.keys():
                # for block in message['blocks']:
                #     if 'text' in block.keys():
                #         if block['text'] == message_to_check:
                for block in blocks_to_check:
                    if 'text' in block.keys():
                        if 'UPCOMING EVENTS' in block['text']['text'] or 'ONGOING ISSUES' in block['text']['text']:
                            continue
                        messages_to_check.append(re.sub("`.*?`","",block['text']['text']))
                for block in message['blocks']:
                    if 'text' in block.keys():
                        old_message = block['text']['text']
                        old_message = re.sub("`.*?`","",old_message)
                        old_message = re.sub("<","",old_message)
                        old_message = re.sub(">","",old_message)
                        for message_to_check in messages_to_check:
                            if message_to_check == old_message:
                                return False
        return True

    except SlackApiError as e:
        logger.error("Error creating conversation: {}".format(e))



def get_events():
    if mode == 'issues':
        start_date = (date.today() - timedelta(hours=12)).isoformat()
        text = ":alert: |   *ONGOING ISSUES*  | :alert: "
        filter ={
         'eventTypeCategories': [
            'issue'
        ],
        'eventStatusCodes': [
            'open', 'closed'
        ],
        'startTimes': [
            {
                'from': start_date
            },
        ]
        }
    if mode == 'scheduled':
        end_date = (date.today() + timedelta(days=7)).isoformat()
        start_date = (date.today()).isoformat()
        text = f":calendar: |   *{env} - UPCOMING EVENTS*  | :calendar: "
        filter ={
        'eventTypeCategories': [
                'scheduledChange',
            ],
        'startTimes': [
            {
                'from': start_date,
                'to': end_date
            },
        ]
        }
    events =  client.describe_events(
        filter =filter
    )
    arns = []
    for event in events['events']:
        arn = event['arn']
        arns.append(arn)
    blocks = []
    #event_block['text']['text'] = ":calendar: |   *UPCOMING EVENTS*  | :calendar: " 
    if arns:
        describe_events  = client.describe_event_details(eventArns=arns)
        block = {  
            "type": "section",
            "text": {  
                "type": "mrkdwn",
                "text": text
            }
            }
        blocks.append(block)
        for event in describe_events['successfulSet']:  
            if not 'endTime' in event['event']:
                event['event']['endTime'] = "ONGOING"
            block_text = f"`{event['event']['startTime']} -> {event['event']['endTime']}` *{event['event']['service']} - {event['event']['region']} * {event['eventDescription']['latestDescription']}"
            if len(block_text)>2000:
                block_text = block_text[:min(len(block_text), 1800)] + " *THE TEXT WAS TRUNCATED, PLEASE GO TO AWS FOR MORE DETAILS!*"
            block = {  
            "type": "section",
            "text": {  
                "type": "mrkdwn",
                "text": block_text
            }
            }
            blocks.append(block)
            blocks.append(
                {
                "type": "divider"
                }
            )
        if mode == 'issues' and check_old_messages(blocks):
            post_message_to_slack(blocks)
        elif mode == 'scheduled':
            post_message_to_slack(blocks)

if __name__ == "__main__":
    get_events()


 
