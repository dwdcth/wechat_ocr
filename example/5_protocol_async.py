"""示例 5: 协议级异步 (对应 swigger/wechat-ocr 的 doOCR(nullptr) + wait_done)

mojo 消息天然异步: 提交即返回, 结果经 10011 推送按完成顺序流入回调。
路径版在途上限 32 (任务队列), Shared 版同刻仅 1。

运行: PYTHONPATH=.. python3 example/5_protocol_async.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from wechat_ocr.ocr_manager import OcrManager

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test_img")


def main():
    done = []

    def on_result(img_path: str, r: dict):
        done.append((img_path, r))
        n = len(r.get("ocrResult", []))
        first = r["ocrResult"][0]["text"][:24] if n else ""
        print(f"  [回调#{len(done)}] {os.path.basename(img_path)}: "
              f"err={r['errcode']} 文字{n}行 {first!r}")

    ocr_manager = OcrManager()
    ocr_manager.SetOcrResultCallback(on_result)
    ocr_manager.StartWeChatOCR()

    paths = [os.path.join(TEST_DIR, n)
             for n in ("1.png", "2.png", "3.png", "qrcode.png", "barcode.png")]

    # 1) 批量提交: 发射后不管 (队列满自动背压等待)
    t0 = time.time()
    ocr_manager.DoOCRTasks(paths)
    print(f"提交 {len(paths)} 张 (在途 {ocr_manager.PendingCount()}), 立即返回 "
          f"耗时 {time.time()-t0:.3f}s")

    # 2) 期间可穿插零拷贝任务 (Shared 通路, 独立于路径队列)
    try:
        from PIL import Image
        img = Image.open(paths[0]).convert("RGBA")
        ocr_manager.DoOCRTaskShared(img.tobytes(), *img.size)
        print("穿插 Shared 零拷贝任务 (在途 %d)" % ocr_manager.PendingCount())
    except ImportError:
        print("(未装 Pillow, 跳过 Shared 演示)")

    # 3) 收尾: 等全部在途完成 (对应 wait_done)
    ok = ocr_manager.WaitDone(timeout=30)
    print(f"WaitDone: {'全部完成' if ok else '超时'}, 共回调 {len(done)} 个结果")

    ocr_manager.KillWeChatOCR()


if __name__ == "__main__":
    main()
