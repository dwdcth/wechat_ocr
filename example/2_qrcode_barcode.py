"""示例 2: 二维码 / 条形码识别

二维码: 结果在 results["qrcode"], 含解码内容 + 四角点像素坐标,
        一张图里有多个二维码会全部返回, 坐标可用于打码/贴图/再生成。
条形码: (EAN-13 等) 的数字会被 OCR 当作文本行识别, 在 results["ocrResult"] 里。

运行: uv run --with protobuf python example/2_qrcode_barcode.py
"""
import os
import time

from wechat_ocr.ocr_manager import OcrManager, OCR_MAX_TASK_ID

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test_img")


def main():
    results = {}

    def cb(img_path: str, r: dict):
        results[img_path] = r

    ocr_manager = OcrManager()
    ocr_manager.SetOcrResultCallback(cb)
    ocr_manager.StartWeChatOCR()
    ocr_manager.DoOCRTask(os.path.join(TEST_DIR, "qrcode.png"))    # 二维码
    ocr_manager.DoOCRTask(os.path.join(TEST_DIR, "barcode.png"))   # 条形码 (EAN-13)
    while ocr_manager.m_task_id.qsize() != OCR_MAX_TASK_ID:
        time.sleep(0.1)
    ocr_manager.KillWeChatOCR()

    for path, r in results.items():
        print(f"=== {os.path.basename(path)} ===")

        # --- 条形码: 数字在 ocrResult 文本行里 (纯数字且较长的行即条码值) ---
        for item in r.get("ocrResult", []):
            t = item["text"].strip()
            if t.isdigit() and len(t) >= 8:
                print(f"  [条形码] {t}  位置={item['location']}")

        # --- 二维码: qrcode 字段, 内容 + 四角点坐标 ---
        for qr in r.get("qrcode", []):
            c = qr["corners"]
            print(f"  [二维码] {qr['text']!r}  type={qr['type']}")
            print(f"           角点: 左上{c['topleft']} 右上{c['topright']} "
                  f"右下{c['bottomright']} 左下{c['bottomleft']}")

        # 提示: 拿到角点后可这样算外接矩形, 用于打码或贴新图:
        #   xs = [c[k]['x'] for k in ('topleft','topright','bottomright','bottomleft')]
        #   ys = [c[k]['y'] for k in ('topleft','topright','bottomright','bottomleft')]
        #   box = (min(xs), min(ys), max(xs), max(ys))


if __name__ == "__main__":
    main()
