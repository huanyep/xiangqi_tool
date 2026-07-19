"""
手机联动服务端

启动: python server.py
手机浏览器访问: http://电脑IP:5800

架构:
  手机浏览器 → WebSocket → FastAPI → YOLO检测 → Pikafish引擎 → 回传结果
"""

import sys, os, asyncio, json, base64
from pathlib import Path
from io import BytesIO

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import uvicorn
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    print("请安装依赖: pip install fastapi uvicorn python-multipart websockets")

import numpy as np
import cv2

from vision.yolo_detector import YOLODetector
from engine.pikafish_engine import PikafishEngine
from core.converter import uci_to_chinese

# ─── 初始化引擎和 YOLO ─────────────────────────────────────

yolo = YOLODetector()
engine = PikafishEngine()

if yolo.is_loaded:
    print("[OK] YOLO 已加载")
if engine.start():
    print("[OK] Pikafish 引擎已启动")

app = FastAPI(title="象棋辅助手机联动")

# ─── 网页界面 ─────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>象棋辅助</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #fff; }
.container { max-width: 100vw; min-height: 100vh; padding: 12px; display: flex; flex-direction: column; }
.header { text-align: center; padding: 8px; font-size: 18px; font-weight: bold; color: #4fc3f7; }

/* 走法卡片 */
.move-card {
    background: rgba(255,255,255,0.08); border-radius: 16px;
    padding: 20px; margin: 8px 0; text-align: center;
    backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1);
}
.move-label { font-size: 13px; color: #888; margin-bottom: 6px; }
.move-text { font-size: 36px; font-weight: bold; color: #4fc3f7; letter-spacing: 2px; }

/* 状态信息 */
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 8px 0; }
.info-item {
    background: rgba(255,255,255,0.05); border-radius: 12px;
    padding: 12px; text-align: center;
}
.info-value { font-size: 20px; font-weight: bold; }
.info-value.red { color: #f44336; }
.info-value.green { color: #4caf50; }
.info-label { font-size: 11px; color: #888; margin-top: 2px; }

/* PV 行 */
.pv-box {
    background: rgba(255,255,255,0.05); border-radius: 12px;
    padding: 12px; margin: 8px 0; font-size: 14px; color: #aaa;
    font-family: monospace; min-height: 20px; word-break: break-all;
}

/* 控制区 */
.controls { display: flex; gap: 10px; margin: 12px 0; }
.btn {
    flex: 1; padding: 14px; border: none; border-radius: 12px;
    font-size: 16px; font-weight: bold; cursor: pointer; transition: all 0.2s;
}
.btn-primary { background: #4fc3f7; color: #000; }
.btn-primary.active { background: #f44336; }
.btn-secondary { background: rgba(255,255,255,0.1); color: #fff; }
.btn:active { transform: scale(0.96); opacity: 0.8; }

/* 状态提示 */
.status-bar {
    text-align: center; padding: 8px; font-size: 12px; color: #666;
    border-radius: 8px; background: rgba(255,255,255,0.03); margin: 4px 0;
}
.status-bar.connected { color: #4caf50; }
.status-bar.disconnected { color: #f44336; }

/* 日志 */
.log-box {
    background: rgba(0,0,0,0.3); border-radius: 8px;
    padding: 8px; font-size: 11px; color: #666; font-family: monospace;
    max-height: 100px; overflow-y: auto; margin-top: auto;
}
.log-box div { padding: 1px 0; }

/* 棋盘预览 */
#preview { display: none; }
.preview-container {
    position: relative; margin: 8px 0; border-radius: 12px; overflow: hidden;
}
.preview-container img { width: 100%; display: block; }
</style>
</head>
<body>
<div class="container">
    <div class="header">♔ 象棋辅助</div>

    <div class="status-bar" id="status">未连接</div>

    <div class="move-card">
        <div class="move-label">推荐走法</div>
        <div class="move-text" id="moveText">--</div>
    </div>

    <div class="info-grid">
        <div class="info-item">
            <div class="info-value" id="scoreValue">0.0</div>
            <div class="info-label">局面评分</div>
        </div>
        <div class="info-item">
            <div class="info-value" id="depthValue">0</div>
            <div class="info-label">搜索深度</div>
        </div>
    </div>

    <div class="pv-box" id="pvLine">等待分析...</div>

    <div class="controls">
        <button class="btn btn-primary" id="btnToggle" onclick="toggleCapture()">▶ 自动</button>
        <button class="btn btn-secondary" onclick="document.getElementById('fileInput').click()">📷 选图</button>
        <input type="file" id="fileInput" accept="image/*" style="display:none" onchange="uploadFile(event)">
    </div>

    <div class="log-box" id="log"></div>
</div>

<script>
let ws = null;
let isCapturing = false;
let captureTimer = null;

function log(msg) {
    const el = document.getElementById('log');
    const div = document.createElement('div');
    div.textContent = '[' + new Date().toLocaleTimeString() + '] ' + msg;
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
}

function setStatus(text, type) {
    const el = document.getElementById('status');
    el.textContent = text;
    el.className = 'status-bar ' + type;
}

// ─── WebSocket ──────────────────────────────────────────

function connectWS() {
    const wsUrl = 'ws://' + location.host + '/ws';
    ws = new WebSocket(wsUrl);
    ws.onopen = () => { setStatus('已连接', 'connected'); log('已连接到电脑'); };
    ws.onclose = () => { setStatus('连接断开', 'disconnected'); log('连接断开'); };
    ws.onerror = () => { setStatus('连接错误', 'disconnected'); };
    ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === 'analysis') {
            document.getElementById('moveText').textContent = data.best_move || '--';
            document.getElementById('scoreValue').textContent = data.score_display || '0.0';
            document.getElementById('scoreValue').className = 'info-value ' + (data.score_color || '');
            document.getElementById('depthValue').textContent = data.depth || '0';
            document.getElementById('pvLine').textContent = data.pv || '';
        } else if (data.type === 'error') {
            log('错误: ' + data.message);
        }
    };
}
connectWS();

// ─── 方式1: HTTPS → getDisplayMedia 自动截屏 ──────────────

let mediaStream = null;
let video = document.createElement('video');

async function tryStartScreenCapture() {
    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
            log('当前浏览器不支持自动截屏');
            return false;
        }
        mediaStream = await navigator.mediaDevices.getDisplayMedia({
            video: { width: { ideal: 720 } }, audio: false
        });
        video.srcObject = mediaStream;
        await video.play();
        mediaStream.getVideoTracks()[0].onended = () => stopCapture();
        return true;
    } catch (e) {
        log('自动截屏不可用 (需要 HTTPS): ' + e.message);
        return false;
    }
}

function captureFrame() {
    if (!video || !video.videoWidth) return null;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    return canvas.toDataURL('image/jpeg', 0.85);
}

// ─── 方式2: 手动选图上传 ──────────────────────────────────

async function uploadFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    log('上传截图: ' + file.name);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch('/analyze', { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.best_move) {
            document.getElementById('moveText').textContent = data.best_move;
            document.getElementById('scoreValue').textContent = data.score_display || '0.0';
            document.getElementById('scoreValue').className = 'info-value ' + (data.score_color || '');
            document.getElementById('depthValue').textContent = data.depth || '0';
            document.getElementById('pvLine').textContent = data.pv || '';
            log('分析完成');
        } else {
            log('未识别到棋盘');
        }
    } catch (e) {
        log('上传失败: ' + e.message);
    }
    event.target.value = '';
}

// ─── 控制 ──────────────────────────────────────────────

function toggleCapture() {
    const btn = document.getElementById('btnToggle');
    if (isCapturing) { stopCapture(); return; }

    tryStartScreenCapture().then(ok => {
        if (ok) {
            isCapturing = true;
            btn.textContent = '⏹ 停止';
            btn.classList.add('active');
            log('自动分析已启动 (每2秒)');
            captureTimer = setInterval(() => {
                const data = captureFrame();
                if (data && ws && ws.readyState === WebSocket.OPEN)
                    ws.send(JSON.stringify({ type: 'frame', image: data }));
            }, 2000);
        } else {
            log('自动模式不可用, 请使用"选图"按钮手动上传截屏');
        }
    });
}

function stopCapture() {
    isCapturing = false;
    document.getElementById('btnToggle').textContent = '▶ 自动';
    document.getElementById('btnToggle').classList.remove('active');
    if (captureTimer) { clearInterval(captureTimer); captureTimer = null; }
    if (mediaStream) { mediaStream.getTracks().forEach(t => t.stop()); mediaStream = null; }
    log('已停止');
}

// ─── 保活 ──────────────────────────────────────────────

setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN)
        ws.send(JSON.stringify({ type: 'ping' }));
}, 15000);

window.addEventListener('beforeunload', () => { stopCapture(); if (ws) ws.close(); });
</script>
</body>
</html>"""


# ─── 路由 ─────────────────────────────────────────────────

@app.get("/")
async def index():
    return HTMLResponse(HTML_TEMPLATE)


@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    """POST 方式上传图片分析"""
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse({"error": "图片解析失败"}, status_code=400)

    result = _process_image(img)
    return JSONResponse(result)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时分析"""
    await websocket.accept()
    print(f"[WS] 手机已连接")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "frame":
                # 解码 base64 图片
                img_data = msg["image"].split(",")[1] if "," in msg["image"] else msg["image"]
                img_bytes = base64.b64decode(img_data)
                nparr = np.frombuffer(img_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if img is not None:
                    result = _process_image(img)
                    await websocket.send_json({"type": "analysis", **result})
                else:
                    await websocket.send_json({"type": "error", "message": "图片解码失败"})

            elif msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        print(f"[WS] 手机已断开")


# ─── 核心分析 ─────────────────────────────────────────────

def _process_image(img: np.ndarray) -> dict:
    """对图像执行 YOLO + Pikafish 全链路分析"""
    # 1. YOLO 检测
    detections = yolo.detect(img, conf_thresh=0.5)
    if not detections:
        return {"best_move": "--", "score": 0, "score_display": "0.0",
                "score_color": "", "depth": 0, "pv": "", "fen": ""}

    fen = yolo.board_to_fen(detections)
    if not fen:
        return {"best_move": "--", "score": 0, "score_display": "0.0",
                "score_color": "", "depth": 0, "pv": "", "fen": ""}

    # 2. Pikafish 分析
    engine.set_position(fen)
    best_move = engine.go(movetime=1500)

    if not best_move or best_move == "(none)" or len(best_move) < 4:
        return {"best_move": "--", "score": 0, "score_display": "0.0",
                "score_color": "", "depth": 0, "pv": "", "fen": fen}

    # 3. 结果格式化
    chinese_move = uci_to_chinese(best_move, fen)
    display_move = chinese_move if chinese_move and '-' not in chinese_move else best_move

    score = engine._info.get("score", 0)
    depth = engine._info.get("depth", 0)
    pv = engine._info.get("pv", "")

    if abs(score) >= 10000:
        score_display = f"{'#' if score > 0 else '-#'}{abs(score)//10000}"
    else:
        score_display = f"{score/100:.1f}"
    score_color = "red" if score < 0 else "green"

    return {
        "best_move": display_move,
        "score": score,
        "score_display": score_display,
        "score_color": score_color,
        "depth": depth,
        "pv": pv[:60] if pv else "",
        "fen": fen,
    }


# ─── 启动 ─────────────────────────────────────────────────

if __name__ == "__main__":
    if not HAS_FASTAPI:
        print("请安装依赖: pip install fastapi uvicorn python-multipart websockets")
        sys.exit(1)

    # 获取所有本机 IP 地址
    import socket
    ips = []
    try:
        # 获取所有网络接口的 IP
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except:
        pass
    try:
        # 另一种方式
        import subprocess
        result = subprocess.run(['ipconfig'], capture_output=True, text=True, encoding='gbk')
        for line in result.stdout.split('\n'):
            if 'IPv4' in line or 'IP Address' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    ip = parts[1].strip()
                    if ip not in ips and not ip.startswith("127."):
                        ips.append(ip)
    except:
        # 备选
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if ip not in ips:
                ips.append(ip)
        except:
            ips.append("无法检测")

    print(f"\n{'='*50}")
    print(f"  象棋辅助 — 手机联动服务端")
    print(f"{'='*50}")
    print(f"  电脑 IP 地址:")
    for ip in ips:
        print(f"    http://{ip}:5800")
    print(f"  本机: http://localhost:5800")
    print(f"{'='*50}")
    print(f"  [!] 如果手机打不开:")
    print(f"  1. 检查手机和电脑是否在同一个 WiFi")
    print(f"  2. 防火墙拦截 → 管理员终端执行:")
    print(f'     netsh advfirewall firewall add rule name="chess-assist" dir=in protocol=tcp localport=5800 action=allow')
    print(f"{'='*50}")
    print(f"  手机操作:")
    print(f"  1. 象棋软件走棋后, 手机截屏 (电源+音量下)")
    print(f"  2. 浏览器中点「选图」, 选最新截屏")
    print(f"  3. 查看走法建议")
    print(f"{'='*50}\n")

    uvicorn.run(app, host="0.0.0.0", port=5800, log_level="warning")
