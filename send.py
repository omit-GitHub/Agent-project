# -*- coding: utf-8 -*-
"""GUIAgent 单指令收发。三种载体,指令字节完全一致(NDJSON 一问一答):

  - tcp  (默认): PC 经 adb 隧道 -> 设备抽象 socket。
                前置: adb forward tcp:8321 localabstract:@guiagent
  - local: 设备本机进程直连抽象 socket @guiagent,不经 adb/TCP。
                AF_UNIX abstract 地址 = '\0' + "@guiagent"
  - ws   : WebSocket(载体 C)。APP 内建 ws 服务端监听 0.0.0.0:8322,
                路径 /guiagent。内网任意可信机器直连,无需 adb forward。
                前置: 设备已开无障碍服务(ws 服务随 onServiceConnected 起)。

切换方式(任一):
  1) 环境变量:  GUIAGENT_TRANSPORT=ws            (或 tcp / local)
  2) 调用参数:  send(req, transport="ws")        (优先级高于 local)
  3) CLI 开关:  python send.py --ws '<json>'     (或 --local)

  ws 连接参数(可选环境变量):
      GUIAGENT_WS_HOST (默认 127.0.0.1,PC 经 adb 隧道用此;直连设备填设备内网 IP)
      GUIAGENT_WS_PORT (默认 8322)
      GUIAGENT_WS_PATH (默认 /guiagent)

用法:
  python send.py '{"id":"1","op":"ping","args":{}}'                   # 默认 tcp
  python send.py --local '{"id":"1","op":"ping","args":{}}'           # 本机直连
  python send.py --ws '{"id":"1","op":"ping","args":{}}'              # ws(默认 host 127.0.0.1,需自行 adb forward tcp:8322 tcp:8322 或填设备 IP)
  GUIAGENT_TRANSPORT=ws GUIAGENT_WS_HOST=192.168.1.10 python send.py  # 直连设备 IP

run-*.py 只调用 send(req),故设 GUIAGENT_TRANSPORT=ws 即可在 ws 载体下跑,
序列逻辑一字不改。
"""
import os, socket, sys, json, struct, base64, hashlib

HOST, PORT = "127.0.0.1", 8321
ABSTRACT_NAME = "@guiagent"            # CommandServer: new LocalServerSocket("@" + "guiagent")
UNIX_ADDR = "\0" + ABSTRACT_NAME       # AF_UNIX abstract: \0 + 名字(含 @)

# WebSocket(载体 C)默认参数
WS_HOST = os.environ.get("GUIAGENT_WS_HOST", "127.0.0.1")
WS_PORT = int(os.environ.get("GUIAGENT_WS_PORT", "8322"))
WS_PATH = os.environ.get("GUIAGENT_WS_PATH", "/guiagent")


def _env_transport():
    return os.environ.get("GUIAGENT_TRANSPORT", "tcp").lower()


def send(req, timeout=15, local=None, transport=None):
    """发一条 NDJSON 指令,返回一行响应 dict。
    transport: None=读环境变量; "tcp"/"local"/"ws"。
    local: True 等价 transport="local"(向后兼容);优先级低于显式 transport。"""
    if transport is None:
        transport = _env_transport()
    if local:  # 显式 local 仍生效
        transport = "local"

    line = json.dumps(req, ensure_ascii=False)

    if transport == "ws":
        resp = _ws_send_recv(line, WS_HOST, WS_PORT, WS_PATH, timeout)
        return json.loads(resp) if resp else {}

    if transport == "local":
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(UNIX_ADDR)
    else:  # tcp (adb 隧道)
        s = socket.create_connection((HOST, PORT), timeout=timeout)
    try:
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


def _ws_send_recv(line, host, port, path, timeout=15):
    """WebSocket 客户端:握手 + 发一掩码文本帧 + 收一(服务端不掩码)文本帧,返回响应行。"""
    s = socket.create_connection((host, port), timeout=timeout)
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        hs = ("GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\n"
              "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
              "Sec-WebSocket-Version: 13\r\n\r\n") % (path, host, port, key)
        s.sendall(hs.encode("utf-8"))
        buf = b""
        while b"\r\n\r\n" not in buf:
            c = s.recv(4096)
            if not c:
                raise IOError("ws handshake: connection closed")
            buf += c
        status = buf.split(b"\r\n", 1)[0]
        if b"101" not in status:
            raise IOError("ws handshake failed: %s" % status.decode("latin-1", "replace"))
        # 校验服务端 Accept(可选,严格对齐 RFC 6455)
        expected = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("utf-8")).digest()
        ).decode()
        if expected.encode() not in buf:
            raise IOError("ws handshake: bad Sec-WebSocket-Accept")

        _ws_send_text(s, line)
        return _ws_recv_text(s)
    finally:
        s.close()


def _ws_send_text(s, text):
    """客户端必须掩码发送。构造 FIN+TEXT 掩码帧。"""
    payload = text.encode("utf-8")
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    header = bytearray([0x81])  # FIN + TEXT
    n = len(payload)
    if n <= 125:
        header.append(0x80 | n)  # mask 位 = 1
    elif n < 65536:
        header.append(0x80 | 126); header += struct.pack(">H", n)
    else:
        header.append(0x80 | 127); header += struct.pack(">Q", n)
    s.sendall(bytes(header) + mask + masked)


def _ws_recv_text(s):
    """读一帧(服务端不掩码);仅取文本帧载荷。"""
    b0 = s.recv(1)
    if not b0:
        raise IOError("ws: connection closed before frame")
    b1 = s.recv(1)
    masked = (b1[0] & 0x80) != 0
    ln = b1[0] & 0x7f
    if ln == 126:
        ln = struct.unpack(">H", _recv_n(s, 2))[0]
    elif ln == 127:
        ln = struct.unpack(">Q", _recv_n(s, 8))[0]
    if masked:
        _recv_n(s, 4)  # 服务端不应掩码;忽略
    data = _recv_n(s, ln)
    return data.decode("utf-8")


def _recv_n(s, n):
    buf = b""
    while len(buf) < n:
        c = s.recv(n - len(buf))
        if not c:
            raise IOError("ws: unexpected eof")
        buf += c
    return buf


if __name__ == "__main__":
    transport = None
    args = sys.argv[1:]
    if args and args[0] == "--local":
        transport = "local"; args = args[1:]
    elif args and args[0] == "--ws":
        transport = "ws"; args = args[1:]
    req = json.loads(args[0]) if args else {"id": "1", "op": "ping", "args": {}}
    print(json.dumps(send(req, transport=transport), ensure_ascii=False, indent=2))
