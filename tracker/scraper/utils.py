import traceback as tb

import requests


def send_message(
    category: str,
    forum: str,
    thread: str,
    title: str,
    description: str,
    color: str = "",
    silent: bool = False,
) -> None:
    if len(title) > 255:
        description = title + "\n" + description
        title = title[:253] + "..."
    data = {
        "category": category,
        "forum": forum,
        "thread": thread,
        "title": title,
        "description": description,
        "silent": silent,
    }

    if color:
        data["color"] = color

    r = requests.post("http://discord:5000/post", json=data)
    if r.status_code != 200:
        raise Exception(f"Failed to send message: {r.text}")


def send_error(
    category: str,
    thread: str,
    title: str,
) -> None:
    send_message(
        category=category,
        forum="errors",
        thread=thread,
        title=title,
        description=tb.format_exc(),
        color="ed1c25",
        silent=False,
    )
