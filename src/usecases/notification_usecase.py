from src.infrastructure.line_client import line_client

def notify_line(message):
    line_client.notify(message)
