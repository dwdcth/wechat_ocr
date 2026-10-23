import os
import json
import time
from wechat_ocr.ocr_manager import OcrManager, OCR_MAX_TASK_ID


def ocr_result_callback(img_path:str, results:dict):
    result_file = os.path.basename(img_path) + ".json"
    print(f"识别成功，img_path: {img_path}, result_file: {result_file}")
    with open(result_file, 'w', encoding='utf-8') as f:
       f.write(json.dumps(results, ensure_ascii=False, indent=2))

def main():
    # 微信路径解析顺序: 显式传参 > 环境变量 > 配置文件 > 常见路径自动探测
    #   - Windows: OcrManager(r"C:\Program Files\Tencent\WeChat")
    #   - Linux:   OcrManager("/opt/wechat-universal")
    #   - macOS:   OcrManager("/Applications/WeChat.app")
    ocr_manager = OcrManager()
    # 可选: 手动指定 OCR 可执行文件路径 (一般无需调用, 自动探测即可)
    # ocr_manager.SetExePath("/opt/wechat-universal/wxocr")
    # 可选: 手动指定微信所在路径 (作为 user-lib-dir 传给子进程)
    # ocr_manager.SetUsrLibDir("/opt/wechat-universal")
    # 设置ocr识别结果的回调函数
    ocr_manager.SetOcrResultCallback(ocr_result_callback)
    # 启动ocr服务
    ocr_manager.StartWeChatOCR()
    # 开始识别图片
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test_img")
    for name in sorted(os.listdir(test_dir)):
        ocr_manager.DoOCRTask(os.path.join(test_dir, name))
    # 等待全部任务完成
    while ocr_manager.m_task_id.qsize() != OCR_MAX_TASK_ID:
        time.sleep(0.1)
    # 识别输出结果
    ocr_manager.KillWeChatOCR()


if __name__ == "__main__":
    main()
