"""推送器：企业微信 webhook / Server酱(微信服务号)。"""
import requests


class WecomPusher:
    """企业微信群机器人 webhook 推送。"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_markdown(self, title: str, body: str) -> bool:
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": f"## {title}\n{body}"},
        }
        resp = requests.post(self.webhook_url, json=payload, timeout=15)
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"企微推送失败: {data}")
        return True

    def send_text(self, content: str) -> bool:
        payload = {"msgtype": "text", "text": {"content": content}}
        resp = requests.post(self.webhook_url, json=payload, timeout=15)
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"企微推送失败: {data}")
        return True


class ServerChanPusher:
    """Server酱(方糖)推送，直接发到微信「方糖」服务号。

    SendKey 形如 SCTxxxx，接口 https://sctapi.ftqq.com/{SendKey}.send
    """

    def __init__(self, send_key: str):
        self.url = f"https://sctapi.ftqq.com/{send_key}.send"

    def send_markdown(self, title: str, body: str) -> bool:
        return self._send(title, body)

    def send_text(self, content: str) -> bool:
        return self._send("作业提醒", content)

    def _send(self, title: str, desp: str) -> bool:
        resp = requests.post(
            self.url, data={"title": title, "desp": desp}, timeout=15
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Server酱推送失败: {data}")
        return True
