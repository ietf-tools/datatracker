from ietf.message.models import Message

def infer_message(s):
    from email import message_from_string

    parsed = message_from_string(s.encode("utf-8"))

    m = Message()
    m.subject = parsed.get("Subject", "").decode("utf-8")
    m.frm = parsed.get("From", "").decode("utf-8")
    m.to = parsed.get("To", "").decode("utf-8")
    m.bcc = parsed.get("Bcc", "").decode("utf-8")
    m.reply_to = parsed.get("Reply-to", "").decode("utf-8")
    m.body = parsed.get_payload().decode("utf-8")

    return m
