"""示例 4: asyncio 异步识别 (批量并发 + 零拷贝)

运行: PYTHONPATH=.. python3 example/4_async.py
(需 Python 3.12+, protobuf; 零拷贝演示需 Pillow)
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from wechat_ocr.ocr_manager import AsyncOcrManager, OCR_MAX_TASK_ID

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test_img")


async def main():
    mgr = AsyncOcrManager()
    mgr.StartWeChatOCR()

    # 1) 批量并发 (路径版, 引擎队列上限 32)
    paths = [os.path.join(TEST_DIR, n)
             for n in ("1.png", "2.png", "3.png", "qrcode.png", "barcode.png")]
    t0 = time.time()
    results = await mgr.ocr_paths(paths, concurrency=8)
    print(f"批量 {len(paths)} 张, 耗时 {time.time()-t0:.2f}s")
    for p, r in zip(paths, results):
        lines = [l["text"] for l in r.get("ocrResult", [])]
        qr = r.get("qrcode") or []
        print(f"  {os.path.basename(p)}: err={r['errcode']} 文字{len(lines)}行 "
              f"码{len(qr)}个 {lines[:1]}{' ' + qr[0]['text'] if qr else ''}")

    # 2) 零拷贝单张 (Shared 通路, 协议限制串行)
    try:
        from PIL import Image
        img = Image.open(os.path.join(TEST_DIR, "1.png")).convert("RGBA")
        r = await mgr.ocr_rgba(img.tobytes(), *img.size)
        print(f"零拷贝: err={r['errcode']} "
              f"首行={r['ocrResult'][0]['text'][:30]!r}" if r.get("ocrResult") else
              f"零拷贝: err={r['errcode']}")
    except ImportError:
        print("(未装 Pillow, 跳过零拷贝演示)")

    # 3) 编码图字节流并发
    datas = [open(p, "rb").read() for p in paths[:3]]
    rs = await asyncio.gather(*(mgr.ocr_bytes(d) for d in datas))
    print(f"bytes 并发: {['err=%d' % r['errcode'] for r in rs]}")

    mgr.KillWeChatOCR()


if __name__ == "__main__":
    asyncio.run(main())
