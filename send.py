# -*- coding: utf-8 -*-
"""GUIAgent 单指令收发。两种载体,指令字节完全一致(NDJSON 一问一答):

  - tcp   (默认): PC 经 adb 隧道 -> 设备抽象 socket。
                前置: adb forward tcp:8321 localabstract:@guiagent
  - local : 设备本机进程直连抽象 socket @guiagent,不经 adb/TCP。
                AF_UNIX abstract 地址 = '\0' + "@guiagent"

切换方式(任一):
  1) 环境变量:  GUIAGENT_TRANSPORT=local
  2) 调用参数:  send(req, local=True)
  3) CLI 开关:  python send.py --local '<json>'

用法:
  python send.py '{"id":"1","op":"ping","args":{}}'                   # 默认 tcp
  python send.py --local '{"id":"1","op":"ping","args":{}}'           # 本机直连
  GUIAGENT_TRANSPORT=local python send.py                            # 本机直连,无参发 ping

run-search.py 只调用 send(req),故设 GUIAGENT_TRANSPORT=local 即可在设备本机跑,
序列逻辑一字不改。
"""
import os, socket, sys, json

HOST, PORT = "127.0.0.1", 8321
ABSTRACT_NAME = "@guiagent"            # CommandServer: new LocalServerSocket("@" + "guiagent")
UNIX_ADDR = "\0" + ABSTRACT_NAME       # AF_UNIX abstract: \0 + 名字(含 @)


def _env_local():
    return os.environ.get("GUIAGENT_TRANSPORT", "tcp").lower() == "local"


def send(req, timeout=15, local=None):
    """发一条 NDJSON 指令,返回一行响应 dict。
    local: None=读环境变量; True=本机抽象 socket; False=TCP(adb 隧道)。"""
    if local is None:
        local = _env_local()
    if local:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(UNIX_ADDR)
    else:
        s = socket.create_connection((HOST, PORT), timeout=timeout)
    try:
        line = json.dumps(req, ensure_ascii=False)
        s.sendall((line + "\n").encode("utf-8"))
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(8192)
            if not chunk:
                break
            buf += chunk
        first = buf.split(b"\n", 1)[0]
        return json.loads(first.decode("utf-8")) if first else {}
    finally:
        s.close()


if __name__ == "__main__":
    local = False
    args = sys.argv[1:]
    if args and args[0] == "--local":
        local = True
        args = args[1:]
    req = json.loads(args[0]) if args else {"id": "1", "op": "ping", "args": {}}
    print(json.dumps(send(req, local=local), ensure_ascii=False, indent=2))
