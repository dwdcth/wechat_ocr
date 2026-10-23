"""示例 3: 敏感信息打码

识别图片后, 自动对以下区域打码 (默认马赛克):
  - 文本命中正则的区域 (内置: 手机号 / 身份证 / 邮箱, 可自定义)
  - 二维码区域 (按四角点外接矩形)

运行: uv run --with protobuf --with pillow python example/3_mosaic.py
(打码需要 Pillow; 若用 pip 安装, 装 "wechat-ocr[mosaic] @ git+..." 会自动带上)
输出: test_img/sensitive.masked.png
"""
import os
import time

from wechat_ocr.ocr_manager import OcrManager, OCR_MAX_TASK_ID
from wechat_ocr.mosaic import apply_mosaic

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test_img")
SRC = os.path.join(TEST_DIR, "sensitive.png")
DST = os.path.join(TEST_DIR, "sensitive.masked.png")


def main():
    # 1. 先做识别
    results = {}

    def cb(img_path: str, r: dict):
        results.update(r)

    ocr_manager = OcrManager()
    ocr_manager.SetOcrResultCallback(cb)
    ocr_manager.StartWeChatOCR()
    ocr_manager.DoOCRTask(SRC)
    while ocr_manager.m_task_id.qsize() != OCR_MAX_TASK_ID:
        time.sleep(0.1)
    ocr_manager.KillWeChatOCR()

    print("识别到:")
    for item in results.get("ocrResult", []):
        print(f"  文本: {item['text']!r}")
    for qr in results.get("qrcode", []):
        print(f"  二维码: {qr['text']!r}")

    # 2. 打码
    #    patterns 可选值:
    #      "default"                 -> 内置正则 (手机号/身份证/邮箱)
    #      [r"1[3-9]\d{9}", ...]     -> 自定义正则列表, 命中即打掉整行文本框
    #      None                      -> 不按文本打, 只打二维码
    img = apply_mosaic(
        SRC, results,
        patterns="default",
        qrcode=True,
        style="pixel",   # pixel 马赛克 | blur 模糊 | solid 纯色
        block=12,        # 马赛克块大小 / 模糊半径
        pad=4,           # 区域外扩像素, 防边缘残留
    )
    img.save(DST)
    print(f"\n打码完成, 已保存: {DST}")


if __name__ == "__main__":
    main()
