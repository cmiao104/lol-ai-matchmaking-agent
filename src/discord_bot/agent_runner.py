import requests

AGENT_URL = "https://chat-agent-api-584885093493.us-central1.run.app/ask"


def run_agent(prompt: str) -> str:
    try:
        response = requests.post(
            AGENT_URL,
            json={"prompt": prompt},
            timeout=90
        )
        response.raise_for_status()

        data = response.json()

        if not data.get("ok", False):
            return f"Agent 调用失败：{data.get('error', '未知错误')}"

        answer = data.get("answer", "")

        if not answer:
            return "Agent 没有返回内容。"

        if len(answer) > 1800:
            answer = answer[:1800] + "\n\n...[输出过长，已截断]"

        return answer

    except requests.Timeout:
        return "远程 agent 调用超时。"

    except requests.RequestException as e:
        return f"远程请求失败：{e}"

    except Exception as e:
        return f"运行出错：{e}"
