"""敏感信息打码示例: 识别 -> 命中正则的文本 + 二维码 全部打码"""
import os
import time
from wechat_ocr.ocr_manager import OcrManager, OCR_MAX_TASK_ID
from wechat_ocr.mosaic import apply_mosaic

IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test_img", "sensitive.png")
OUT = IMG.replace(".png", ".masked.png")


def main():
    results = {}

    def cb(img_path: str, r: dict):
        results.update(r)

    ocr_manager = OcrManager()
    ocr_manager.SetOcrResultCallback(cb)
    ocr_manager.StartWeChatOCR()
    ocr_manager.DoOCRTask(IMG)
    while ocr_manager.m_task_id.qsize() != OCR_MAX_TASK_ID:
        time.sleep(0.1)
    ocr_manager.KillWeChatOCR()

    img = apply_mosaic(
        IMG, results,
        patterns="default",   # 内置: 手机号 / 身份证 / 邮箱; 也可传自定义正则列表
        qrcode=True,          # 二维码区域一并打掉
        style="pixel",        # pixel | blur | solid
        block=12,
    )
    img.save(OUT)
    print(f"打码完成: {OUT}")
    print(f"  打掉文本行 {len(results.get('ocrResult', []))} 条, 二维码 {len(results.get('qrcode', []))} 个")


if __name__ == "__main__":
    main()
