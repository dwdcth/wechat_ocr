"""示例 1: 基础文字识别 (OCR)

运行: uv run --with protobuf python example/1_ocr.py
(在仓库目录下, uv 会自动创建虚拟环境并安装依赖)
"""
import os
import json
import time

from wechat_ocr.ocr_manager import OcrManager, OCR_MAX_TASK_ID

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test_img")


def main():
    results = {}  # img_path -> 识别结果

    def ocr_result_callback(img_path: str, r: dict):
        results[img_path] = r
        print(f"\n=== {os.path.basename(img_path)} (errcode={r['errcode']}) ===")
        for item in r.get("ocrResult", []):
            loc = item["location"]
            print(f"  {item['text']!r}  "
                  f"(置信度 {item['rate']:.2f}, 位置 [{loc['left']:.0f},{loc['top']:.0f},"
                  f"{loc['right']:.0f},{loc['bottom']:.0f}])")

    # 微信路径解析顺序: 显式传参 > 环境变量 > 配置文件 > 自动探测, 一般无需传参
    ocr_manager = OcrManager()
    ocr_manager.SetOcrResultCallback(ocr_result_callback)
    ocr_manager.StartWeChatOCR()

    # 同时可识别普通文本图片 / 二维码图 / 条形码图 / 带敏感信息的截图
    for name in ("1.png", "qrcode.png", "barcode.png"):
        ocr_manager.DoOCRTask(os.path.join(TEST_DIR, name))

    # 等待全部任务完成 (任务队列回到满即全部回调完毕)
    while ocr_manager.m_task_id.qsize() != OCR_MAX_TASK_ID:
        time.sleep(0.1)
    ocr_manager.KillWeChatOCR()

    print(f"\n共识别 {len(results)} 张图片, 完整结果示例:")
    print(json.dumps(next(iter(results.values())), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
