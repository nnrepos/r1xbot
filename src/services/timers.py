
import datetime
import time
import traceback
from typing import Tuple
from infra import logger, utils 
from infra.context import Context
utils.load_env()
import db_models
from services.messengers import messenger_factory

def invoke_alert_tool(ctx:Context, alert_args:Tuple[int, str], parsed_message):
    messenger_chat_id = f"{parsed_message.source}:{parsed_message.chatId}"
    timestamp = int(parsed_message.messageTimestamp.timestamp())
    ref_id = parsed_message.messageId
    
    with db_models.Session() as session:
        now = datetime.datetime.now()
        delta_ts, topic = alert_args
        timer_extra_data = {"topic":topic, "ref_id":ref_id}
        trigger_ts = datetime.datetime.fromtimestamp(timestamp+ int(delta_ts))
        timer = db_models.Timer(
            chat_id=messenger_chat_id,
            trigger_timestamp=trigger_ts, 
            data=timer_extra_data,
            created_at=now,
            updated_at=now
        )

        session.add(timer)
        session.commit()
        session.refresh(timer)

        session.close()

    return timer

def alert_users():
    ctx = Context()
    while True:
        try:
            now = datetime.datetime.utcnow()
            with db_models.Session() as session:
                alerts = session.query(db_models.Timer).filter(db_models.Timer.trigger_timestamp <= now).all()
            if alerts:
                ctx.log(f"[TIMER] found {len(alerts)} alerts")                
                
                for alert in alerts:
                    try:
                        topic = alert.data.get("topic", None)
                        quote_id = alert.data.get("ref_id", None)
                        messenger, chat_id = messenger_factory.get_messenger_and_chat_id(alert.chat_id)
                        ctx.log(f"[TIMER] sending a timer message to chat id {alert.chat_id}")
                        messenger.send_message(ctx, {
                            "chat_id": chat_id, 
                            "kind": "text",
                            "body": f"You asked me to remind you about {topic}" if topic else "You asked me to remind you",
                            "quote_id":quote_id
                        })
                    except:
                        ctx.log(f"[TIMER] failed to send alert {alert.id} to chat id:{alert.chat_id} ")
                delete_alerts(ctx, now)                        
            time.sleep(5)

        except Exception as e:
            logger.logger.error(f'Exception occurred; {e}; stack trace: ', traceback.format_exc()) 

def delete_alerts(ctx:Context, now:datetime.datetime) -> None:
    with db_models.Session() as session:
        session.query(db_models.Timer).filter(db_models.Timer.trigger_timestamp <= now).delete()
        ctx.log("[TIMER] alerts deleted")
        session.commit()   