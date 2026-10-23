## 项目说明
本项目是使用Python来调用微信本地ocr模型，调用方法完全由[QQImpl](https://github.com/EEEEhex/QQImpl)翻译过来。也就是说该项目只是将原C++代码翻译成了纯Python实现。

**现已支持跨平台**: Windows / Linux / macOS (统一使用微信 4.x 协议)。

#### 温馨提示

该项目自己玩玩就行，不要用于商业用途

## 使用说明

#### 安装
`pip install wechat-ocr`

#### 依赖(必要条件)

1. Windows / Linux / macOS 系统
2. 已安装微信 4.x (Linux 为 wechat-universal 等发行版, macOS 为 WeChat.app)
3. Python 3.12+, 以及 `protobuf`

#### 微信路径解析

库会按以下顺序解析微信安装路径 (即包含 `mmmojo` 动态库与 `WeChatOCR`/`wxocr` 可执行文件的目录):

1. **显式传参**: `OcrManager(wechat_path)`
2. **环境变量**: `WECHAT_OCR_DIR` / `WECHAT_OCR_EXE` / `WECHAT_OCR_MMMOJO`
3. **配置文件** (JSON):
   - Linux/macOS: `~/.config/wechat_ocr/config.json` (或 `$XDG_CONFIG_HOME/wechat_ocr/config.json`)
   - Windows: `%APPDATA%\wechat_ocr\config.json`
   - 可用环境变量 `WECHAT_OCR_CONFIG` 直接指定配置文件完整路径

   ```json
   {
       "wechat_dir": "/opt/wechat-universal",
       "ocr_exe_path": "/opt/wechat-universal/wxocr",
       "mmmojo_path": "/opt/wechat-universal/libmmmojo.so"
   }
   ```

   只填 `wechat_dir` 即可，其余两项会在该目录下自动查找。
4. **常见路径自动探测**:
   - Windows: `C:\Program Files\Tencent\WeChat` 等
   - Linux: `/opt/wechat-universal`、`/opt/wechat` 等
   - macOS: `/Applications/WeChat.app`

#### 示例

```python
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
    # 微信路径解析顺序: 显式传参 > 环境变量 > 配置文件 > 自动探测
    #   - Windows: OcrManager(r"C:\Program Files\Tencent\WeChat")
    #   - Linux:   OcrManager("/opt/wechat-universal")
    #   - macOS:   OcrManager("/Applications/WeChat.app")
    ocr_manager = OcrManager()
    # 设置ocr识别结果的回调函数
    ocr_manager.SetOcrResultCallback(ocr_result_callback)
    # 启动ocr服务
    ocr_manager.StartWeChatOCR()
    # 开始识别图片
    ocr_manager.DoOCRTask("test_img/1.png")
    ocr_manager.DoOCRTask("test_img/2.png")
    ocr_manager.DoOCRTask("test_img/3.png")
    # 等待全部任务完成
    while ocr_manager.m_task_id.qsize() != OCR_MAX_TASK_ID:
        time.sleep(0.1)
    # 识别输出结果
    ocr_manager.KillWeChatOCR()


if __name__ == "__main__":
    main()
```

#### 运行结果

![result](./result.png)

#### 识别结果格式 (微信 4.x 协议)

```json
{
  "taskId": 2,
  "errcode": 0,
  "width": 300,
  "height": 60,
  "ocrResult": [
    {
      "text": "你好世界",
      "rate": 0.99,
      "location": {"left": 8.0, "top": 18.0, "right": 202.0, "bottom": 52.0}
    }
  ]
}
```

> 注: 本版本统一使用微信 4.x 的 `ParseOCRReqMessage/ParseOCRRespMessage` 协议
> (request id: 10010/10011), 不再支持微信 3.x 的旧协议。

## 感谢

https://github.com/EEEEhex/QQImpl
https://github.com/swigger/wechat-ocr (Linux/macOS 协议参考)
