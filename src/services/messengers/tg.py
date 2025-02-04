import os
import random
import tempfile
from typing import Optional
import requests

from infra.context import Context
from services.messengers.messenger import MessageKindE, MessagingService
from infra import utils
from box import Box

import threading

TELEGRAM_SENDER_ID = os.environ['TELEGRAM_BOT_TOKEN'].split(':')[0]

class TelegramMessenger(MessagingService):
    
    def _get_message_kind(self, message) -> Optional[str]:
        if 'text' in message:
            return MessageKindE.TEXT
        elif 'voice' in message:
            return MessageKindE.VOICE
        elif 'audio' in message:
            return MessageKindE.AUDIO
        return None

    def parse_message(self, message):
        message = message['message']

        source = "tg"
        message_timestamp = message['date']
        chat_type = message['chat']['type']
        chat_id = str(message['chat']['id'])
        sender_id = str(message['from']['id'])
        is_sent_by_me = message['from']['id'] == int(TELEGRAM_SENDER_ID)
        is_forwarded = message.get('forward_from', None) != None
        messageId = str(message['message_id'])
        reply_to_message_id = message['reply_to_message']['message_id'] if 'reply_to_message' in message else None
        kind = self._get_message_kind(message)
        body = message['text'] if 'text' in message else None
        fileId = message['voice']['file_id'] if kind == MessageKindE.VOICE else None
        fileUniqueId = message['voice']['file_unique_id'] if kind == MessageKindE.VOICE else None

        return (
            Box({
                'source': source,
                'messageTimestamp': message_timestamp,
                'chatType': chat_type,
                'chatId': chat_id,
                'senderId': sender_id,
                'isSentByMe': is_sent_by_me,
                'isForwarded': is_forwarded,
                'messageId': messageId,
                'replyToMessageId': reply_to_message_id,
                'kind': kind,
                'body': body,
                'rawSource': message
            }),
            Box({
                'fileId': fileId,
                'fileUniqueId': fileUniqueId
            })
        )

    def send_message(self, ctx:Context, attributes):
        chat_id = attributes.get('chat_id')
        quote_id = attributes.get('quote_id')
        kind = attributes.get('kind')
        body = attributes.get('body')

        if kind != "text":
            return

        args = {'chat_id': chat_id, 'text': body}
        if quote_id:
            args['reply_to_message_id'] = quote_id
            args['allow_sending_without_reply'] = True

        response = requests.post(
            f'https://api.telegram.org/bot{os.environ["TELEGRAM_BOT_TOKEN"]}/sendMessage',
            json=args
        ).json()

        if not response['ok']:
            return None
        
        message = {'message': response['result']}
        parsed_message, file_info = self.parse_message(message)

        return parsed_message
    
    def send_contact(self, ctx: Context, chat_id:str, name:str, handle:str):
        args = {'chat_id': chat_id, 'text': f'https://t.me/{handle}'}
        response = requests.post(
            f'https://api.telegram.org/bot{os.environ["TELEGRAM_BOT_TOKEN"]}/sendMessage',
            json=args
        ).json()

        return response


    def is_message_for_me(self, msg) -> bool:
        if msg.chatType == "private":
            return True

        if msg.body.startswith(f'@{os.environ["TELEGRAM_BOT_NAME"]}'):
            return True

        if 'reply_to_message' in msg.rawSource and msg.rawSource['reply_to_message']['from']['id'] == int(TELEGRAM_SENDER_ID):
            return True

        return False
    
    
    def get_voice_mp3_file(self, ctx:Context, parsed_message, file_info, work_dir) -> str:
        ctx.log(f"getVoiceMp3File: {parsed_message}, {file_info}, {work_dir}")
        url = self._get_download_url(ctx, file_info.fileId)
        orig_file_path, mp3_file_path = self._get_audio_file_paths(ctx, parsed_message.chatId, file_info, work_dir)

        utils.download_stream_file(ctx, url, orig_file_path)
        utils.convert_audio_to_mp3(ctx, orig_file_path, mp3_file_path)

        return mp3_file_path

    def _get_download_url(self, ctx:Context, file_id):
        args = {"file_id": file_id}

        response = requests.post(
            f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/getFile",
            json=args,
        )
        data = response.json()

        if not data["ok"]:
            ctx.log(f"getDownloadUrl failed. response={data}")

        remote_file_path = data["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{remote_file_path}"

        ctx.log(f"getDownloadUrl: downloadUrl={download_url}")
        return download_url

    def _get_audio_file_paths(self, ctx:Context, chat_id, file_info, work_dir):
        orig_file_path = work_dir / 'audio.orig'
        mp3_file_path = work_dir / 'audio.mp3'

        ctx.log(f"getAudioFilePaths: origFilePath={orig_file_path}, mp3FilePath={mp3_file_path}")

        return orig_file_path, mp3_file_path

    def set_typing(self, chat_id, in_flight):
        if not in_flight["working"]:
            return

        requests.post(
            f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
        )

        base_timeout = 6
        extra_timeout = random.randint(0, 1500)
        timeout = base_timeout + (extra_timeout / 1000)

        timer = threading.Timer(timeout, self.set_typing, args=(chat_id, in_flight))
        timer.start()
    
    def set_status_read(self, ctx: Context, message_id) -> None:
        return
