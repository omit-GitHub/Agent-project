# -*- coding: utf-8 -*-
"""GUIAgent 单指令收发(WebSocket 载体,NDJSON 一问一答):

  APP 内建 ws 服务端监听 0.0.0.0:8322,路径 /guiagent。内网任意可信机器直连,
  无需 adb forward。前置: 设备已开无障碍服务(ws 服务随 onServiceConnected 起)。

  连接参数(可选环境变量):
      GUIAGENT_WS_HOST (默认 127.0.0.1,PC 经 adb 隧道用此;直连设备填设备内网 IP)
      GUIAGENT_WS_PORT (默认 8322)
      GUIAGENT_WS_PATH (默认 /guiagent)

用法:
  # 直连设备 IP(无需 adb)
  set PYTHONUTF8=1
  set GUIAGENT_WS_HOST=192.168.1.10
  python send.py '{"id":"1","op":"ping","args":{}}'
  # 或经 adb 隧道(默认 host 127.0.0.1,先建 forward)
  adb forward tcp:8322 tcp:8322
  python send.py '{"id":"1","op":"ping","args":{}}'

run-*.py 只调用 send(req),设 GUIAGENT_WS_HOST 即可在任意内网机器上跑,
序列逻辑一字不改。
"""
import os, socket, sys, json, struct, base64, hashlib

WS_HOST = os.environ.get("GUIAGENT_WS_HOST", "127.0.0.1")
WS_PORT = int(os.environ.get("GUIAGENT_WS_PORT", "8322"))
WS_PATH = os.environ.get("GUIAGENT_WS_PATH", "/guiagent")


def send(req, timeout=15):
    """发一条 NDJSON 指令,返回一行响应 dict。"""
    line = json.dumps(req, ensure_ascii=False)
    resp = _ws_send_recv(line, WS_HOST, WS_PORT, WS_PATH, timeout)
    return json.loads(resp) if resp else {}


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
    req = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"id": "1", "op": "ping", "args": {}}
    print(json.dumps(send(req), ensure_ascii=False, indent=2))
